from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AuditEvent

router = APIRouter(prefix="/admin/media", tags=["media library"])
EDITOR_ROLES = ("content_editor", "admin", "super_admin")
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
}


class MediaAssetPublic(BaseModel):
    url: HttpUrl
    path: str
    bucket: str
    content_type: str
    size_bytes: int


def _detect_image(payload: bytes) -> tuple[str, str] | None:
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
        raise HTTPException(status_code=413, detail="Choose an image smaller than 10 MB")
    image = _detect_image(payload)
    if image is None:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP image")
    content_type, extension = image
    bucket = settings.supabase_public_media_bucket.strip()
    storage_path = f"cms/{uuid4().hex}{extension}"
    storage_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{storage_path}"
    try:
        response = httpx.put(
            storage_url,
            content=payload,
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": content_type,
                "x-upsert": "false",
                "cache-control": "31536000",
            },
            timeout=25,
            follow_redirects=False,
        )
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="Supabase Storage upload timed out") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Could not connect to Supabase Storage") from error
    if response.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Supabase Storage rejected the upload; check the bucket and server key")
    public_url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{storage_path}"
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="media.uploaded",
        entity_type="media_asset",
        entity_id=storage_path,
        change_summary={"content_type": content_type, "size_bytes": len(payload)},
    ))
    session.commit()
    return MediaAssetPublic(url=public_url, path=storage_path, bucket=bucket, content_type=content_type, size_bytes=len(payload))
