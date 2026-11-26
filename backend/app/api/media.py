import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AuditEvent

logger = logging.getLogger(__name__)
ROUTER_TAG = "media library"
router = APIRouter(prefix="/admin/media", tags=["media library"])
EDITOR_ROLES = ("content_editor", "admin", "super_admin")
MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "application/pdf": (b"%PDF-", ".pdf"),
}


async def _ensure_public_bucket(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    service_role_key: str,
    bucket: str,
) -> bool:
    """Create the public Storage bucket via Service Role when Supabase reports it missing."""
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    create_resp = await client.post(
        f"{base_url}/storage/v1/bucket",
        json={"id": bucket, "name": bucket, "public": True},
        headers=headers,
    )
    if create_resp.status_code in (200, 201, 409):
        return True
    logger.warning(
        "Supabase Storage bucket auto-create failed bucket=%s status=%s body=%r",
        bucket,
        create_resp.status_code,
        (create_resp.text or "")[:200],
    )
    return False


class MediaAssetPublic(BaseModel):
    url: HttpUrl
    path: str
    bucket: str
    content_type: str
    size_bytes: int


def _detect_media(payload: bytes) -> tuple[str, str] | None:
    for content_type, (signature, extension) in ALLOWED_SIGNATURES.items():
        if payload.startswith(signature):
            return content_type, extension
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


@router.post("/upload", response_model=MediaAssetPublic, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*EDITOR_ROLES)),
) -> MediaAssetPublic:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key or not settings.supabase_public_media_bucket:
        raise HTTPException(status_code=503, detail="Configure Supabase Storage server settings before uploading media")
    payload = await file.read(MAX_FILE_BYTES + 1)
    if not payload or len(payload) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Choose a file smaller than 20 MB")
    detected = _detect_media(payload)
    if detected is None:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, WebP image, or PDF document")
    content_type, extension = detected
    base_url = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_public_media_bucket.strip()
    storage_path = f"cms/{uuid4().hex}{extension}"
    storage_url = f"{base_url}/storage/v1/object/{bucket}/{storage_path}"
    upload_headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": content_type,
        "x-upsert": "false",
        "cache-control": "31536000",
    }
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
            response = await client.put(storage_url, content=payload, headers=upload_headers)
            if response.status_code in (400, 404) and "bucket" in (response.text or "").lower():
                if await _ensure_public_bucket(
                    client,
                    base_url=base_url,
                    service_role_key=settings.supabase_service_role_key,
                    bucket=bucket,
                ):
                    response = await client.put(storage_url, content=payload, headers=upload_headers)
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="Supabase Storage upload timed out") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Could not connect to Supabase Storage") from error
    if response.status_code not in (200, 201):
        logger.warning(
            "Supabase Storage upload rejected bucket=%s status=%s body=%r",
            bucket,
            response.status_code,
            (response.text or "")[:200],
        )
        raise HTTPException(status_code=502, detail="Supabase Storage rejected the upload; check the bucket and server key")
    public_url = f"{base_url}/storage/v1/object/public/{bucket}/{storage_path}"
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="media.uploaded",
        entity_type="media_asset",
        entity_id=storage_path,
        change_summary={"content_type": content_type, "size_bytes": len(payload)},
    ))
    session.commit()
    return MediaAssetPublic(url=public_url, path=storage_path, bucket=bucket, content_type=content_type, size_bytes=len(payload))
