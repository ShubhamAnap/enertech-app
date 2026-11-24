from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AppConfig, AuditEvent, Product, ProductCategory
from app.schemas.cms import BrandContent, ChatContent, ContactContent, ContentEnvelope, HomeContent, SolutionFinderContent

router = APIRouter(tags=["app content"])
CONTENT_SCHEMAS = {
    "home": HomeContent,
    "contacts": ContactContent,
    "solution_finder": SolutionFinderContent,
    "chat": ChatContent,
    "brand": BrandContent,
}
CONTENT_ROLES = ("content_editor", "admin", "super_admin")


def _schema_for(key: str):
    schema = CONTENT_SCHEMAS.get(key)
    if schema is None:
        raise HTTPException(status_code=404, detail="This app-content section is not supported")
    return schema


def _as_envelope(record: AppConfig | None, key: str) -> ContentEnvelope:
    schema = _schema_for(key)
    if record is None:
        defaults = schema().model_dump(mode="json")
        return ContentEnvelope(key=key, draft_payload=defaults, published_payload=None, draft_revision=0, published_revision=None, updated_at=None)
    draft_payload = schema.model_validate(record.draft_payload).model_dump(mode="json")
    published_payload = schema.model_validate(record.published_payload).model_dump(mode="json") if record.published_payload is not None else None
    return ContentEnvelope(
        key=record.key,
        draft_payload=draft_payload,
        published_payload=published_payload,
        draft_revision=record.draft_revision,
        published_revision=record.published_revision,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.get("/app/config")
def public_app_config(session: Session = Depends(get_session)) -> dict[str, object]:
    records = session.scalars(select(AppConfig).where(AppConfig.published_payload.is_not(None)))
    result = {record.key: record.published_payload for record in records if record.key in CONTENT_SCHEMAS}
    chat = result.get("chat")
    settings = get_settings()
    if isinstance(chat, dict) and chat.get("enabled"):
        public_chat = {**chat, "allowed_hosts": sorted(settings.allowed_chat_hosts)}
        if chat.get("integration") == "hosted_widget":
            public_chat.update({
                "widget_script_url": chat.get("widget_script_url") or settings.chat_widget_script_url,
                "widget_public_key": settings.chat_widget_public_key,
            })
        result["chat"] = public_chat
    return result


@router.get("/admin/app-config/{key}", response_model=ContentEnvelope)
def read_app_config(
    key: str,
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ContentEnvelope:
    _schema_for(key)
    return _as_envelope(session.scalar(select(AppConfig).where(AppConfig.key == key)), key)


@router.put("/admin/app-config/{key}", response_model=ContentEnvelope)
def save_app_config(
    key: str,
    payload: dict[str, object],
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ContentEnvelope:
    schema = _schema_for(key)
    try:
        validated = schema.model_validate(payload).model_dump(mode="json")
    except Exception as error:
        raise HTTPException(status_code=422, detail="App content did not pass validation") from error

    record = session.scalar(select(AppConfig).where(AppConfig.key == key))
    if record is None:
        record = AppConfig(key=key, draft_payload=validated, draft_revision=1, updated_by=admin.uid)
        session.add(record)
    else:
        record.draft_payload = validated
        record.draft_revision += 1
        record.updated_by = admin.uid
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="app_content.draft_saved",
        entity_type="app_config",
        entity_id=key,
        change_summary={"draft_revision": record.draft_revision},
    ))
    session.commit()
    session.refresh(record)
    return _as_envelope(record, key)


@router.post("/admin/app-config/{key}/publish", response_model=ContentEnvelope)
def publish_app_config(
    key: str,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("admin", "super_admin", "content_editor")),
) -> ContentEnvelope:
    schema = _schema_for(key)
    record = session.scalar(select(AppConfig).where(AppConfig.key == key))
    if record is None:
        raise HTTPException(status_code=404, detail="Save a draft before publishing")
    try:
        validated = schema.model_validate(record.draft_payload).model_dump(mode="json")
    except Exception as error:
        raise HTTPException(status_code=422, detail="App content did not pass validation") from error

    if key == "home":
        home = HomeContent.model_validate(validated)
        for category_id in home.featured_category_ids:
            category = session.get(ProductCategory, category_id)
            if category is None or not category.is_published:
                raise HTTPException(status_code=422, detail="Featured collections must be published before they can appear on Home")
        for product_id in home.featured_product_ids:
            product = session.get(Product, product_id)
            if product is None or not product.is_published:
                raise HTTPException(status_code=422, detail="Featured products must be published before they can appear on Home")

    if key == "chat":
        chat = ChatContent.model_validate(validated)
        if chat.enabled:
            if chat.embed_url is None:
                raise HTTPException(status_code=422, detail="Add the approved chat embed URL before enabling chat")
            host = urlparse(str(chat.embed_url)).hostname
            allowed = get_settings().allowed_chat_hosts
            if not host or host.lower() not in allowed:
                raise HTTPException(status_code=422, detail="The chat URL host is not in the server-side CHAT_ALLOWED_HOSTS allowlist")
            if chat.integration == "hosted_widget":
                script_url = str(chat.widget_script_url or get_settings().chat_widget_script_url)
                script_host = urlparse(script_url).hostname
                if not script_url.startswith("https://") or not script_host or script_host.lower() not in allowed:
                    raise HTTPException(status_code=422, detail="Set the widget script URL to HTTPS on a host included in CHAT_ALLOWED_HOSTS")
                if not get_settings().chat_widget_public_key:
                    raise HTTPException(status_code=422, detail="Configure CHAT_WIDGET_PUBLIC_KEY (the provider's public embed key) before publishing the widget")
            if chat.human_handoff_enabled:
                handoff_url = str(chat.human_handoff_url or "")
                handoff_host = urlparse(handoff_url).hostname
                if not handoff_url.startswith("https://") or not handoff_host or handoff_host.lower() not in allowed:
                    raise HTTPException(status_code=422, detail="Set the human handoff URL to HTTPS on a host included in CHAT_ALLOWED_HOSTS")

    record.published_payload = validated
    record.published_revision = record.draft_revision
    record.published_by = admin.uid
    record.published_at = datetime.now(timezone.utc)
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="app_content.published",
        entity_type="app_config",
        entity_id=key,
        change_summary={"published_revision": record.draft_revision},
    ))
    session.commit()
    session.refresh(record)
    return _as_envelope(record, key)


@router.post("/admin/app-config/{key}/unpublish", response_model=ContentEnvelope)
def unpublish_app_config(
    key: str,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("admin", "super_admin")),
) -> ContentEnvelope:
    _schema_for(key)
    record = session.scalar(select(AppConfig).where(AppConfig.key == key))
    if record is None:
        raise HTTPException(status_code=404, detail="App content not found")
    record.published_payload = None
    record.published_revision = None
    record.published_at = None
    record.published_by = None
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="app_content.unpublished",
        entity_type="app_config",
        entity_id=key,
        change_summary={"unpublished": True},
    ))
    session.commit()
    session.refresh(record)
    return _as_envelope(record, key)
