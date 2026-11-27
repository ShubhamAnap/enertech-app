from datetime import date, datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AppConfig, AuditEvent, LegalDocumentVersion, Product, ProductCategory
from app.schemas.cms import BrandContent, ChatContent, ContactContent, ContentEnvelope, HomeContent, LegalContent, LegalDocumentPublic, SolutionFinderContent

router = APIRouter(tags=["app content"])
CONTENT_SCHEMAS = {
    "home": HomeContent,
    "contacts": ContactContent,
    "solution_finder": SolutionFinderContent,
    "chat": ChatContent,
    "brand": BrandContent,
    "privacy_policy": LegalContent,
    "terms": LegalContent,
}
LEGAL_TITLES = {"privacy_policy": "Privacy Policy", "terms": "Terms of Use"}
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
    result = {record.key: record.published_payload for record in records if record.key in CONTENT_SCHEMAS and record.key not in LEGAL_TITLES}
    home = result.get("home")
    if isinstance(home, dict):
        visible_collection_ids = {
            str(cid)
            for cid in session.scalars(
                select(ProductCategory.id).where(
                    ProductCategory.is_published.is_(True),
                    ProductCategory.is_app_collection.is_(True),
                )
            )
        }
        result["home"] = {
            **home,
            "featured_category_ids": [
                str(cid) for cid in (home.get("featured_category_ids") or [])
                if str(cid) in visible_collection_ids
            ],
            "featured_product_category_ids": [
                str(cid) for cid in (home.get("featured_product_category_ids") or [])
                if str(cid) in visible_collection_ids
            ],
        }
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


def _published_legal(key: str, session: Session) -> LegalDocumentPublic:
    if key not in LEGAL_TITLES:
        raise HTTPException(status_code=404, detail="Legal page not found")
    config = session.scalar(select(AppConfig).where(AppConfig.key == key))
    if config is None or config.published_payload is None:
        raise HTTPException(status_code=404, detail="This legal page has not been published")
    version = session.scalar(select(LegalDocumentVersion).where(
        LegalDocumentVersion.key == key,
        LegalDocumentVersion.version == config.published_revision,
    ))
    if version is None:
        raise HTTPException(status_code=503, detail="Published legal page is unavailable")
    return LegalDocumentPublic(
        id=version.id, key=key, title=LEGAL_TITLES[key], body=version.body,
        effective_date=version.effective_date, version=version.version,
        published_at=version.published_at.isoformat(),
    )


@router.get("/legal/current", response_model=dict[str, LegalDocumentPublic])
def public_current_legal(session: Session = Depends(get_session)) -> dict[str, LegalDocumentPublic]:
    return {key: _published_legal(key, session) for key in LEGAL_TITLES}


@router.get("/legal/{key}", response_model=LegalDocumentPublic)
def public_legal_page(key: str, session: Session = Depends(get_session)) -> LegalDocumentPublic:
    return _published_legal(key, session)


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

    if key in LEGAL_TITLES:
        legal = LegalContent.model_validate(validated)
        if len(legal.body.strip()) < 50 or legal.effective_date is None:
            raise HTTPException(status_code=422, detail="Add approved legal text and an effective date before publishing")
        if legal.effective_date > date.today():
            raise HTTPException(status_code=422, detail="Effective date cannot be in the future")

    if key == "home":
        home = HomeContent.model_validate(validated)
        for category_id in home.featured_category_ids:
            category = session.get(ProductCategory, category_id)
            if category is None or not category.is_published or not category.is_app_collection:
                raise HTTPException(status_code=422, detail="Featured collections must be published CMS collections before they can appear on Home")
        for category_id in home.featured_product_category_ids:
            category = session.get(ProductCategory, category_id)
            if category is None or not category.is_published or not category.is_app_collection:
                raise HTTPException(status_code=422, detail="Featured products source collections must be published CMS collections before they can appear on Home")
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
    if key in LEGAL_TITLES:
        existing_version = session.scalar(select(LegalDocumentVersion).where(
            LegalDocumentVersion.key == key,
            LegalDocumentVersion.version == record.draft_revision,
        ))
        if existing_version is None:
            session.add(LegalDocumentVersion(
                key=key, version=record.draft_revision, body=validated["body"],
                effective_date=date.fromisoformat(validated["effective_date"]),
                published_at=record.published_at,
            ))
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
    if key in LEGAL_TITLES:
        raise HTTPException(status_code=409, detail="Publish a replacement legal page instead of removing the public page")
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
