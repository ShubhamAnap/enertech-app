from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.db.session import get_session
from app.models import AuditEvent, KnowledgeArticle
from app.schemas.cms import KnowledgeAdmin, KnowledgePatch, KnowledgePublic, KnowledgeWrite

router = APIRouter(tags=["knowledge"])
EDITOR_ROLES = ("content_editor", "admin", "super_admin")


def _payload(article: KnowledgeArticle) -> dict[str, object]:
    return article.draft_data or {
        "slug": article.slug,
        "title": article.title,
        "category": article.category,
        "answer": article.answer,
        "source_reference": article.source_reference,
        "sort_order": article.sort_order,
    }


def _response(article: KnowledgeArticle) -> KnowledgeAdmin:
    values = _payload(article)
    return KnowledgeAdmin(
        id=article.id, slug=str(values["slug"]), title=str(values["title"]),
        category=str(values.get("category", "General")), answer=str(values["answer"]),
        source_reference=values.get("source_reference"), sort_order=int(values.get("sort_order", 0)),
        is_published=article.is_published, has_draft=article.draft_data is not None,
    )


@router.get("/knowledge", response_model=list[KnowledgePublic])
def public_knowledge(session: Session = Depends(get_session)) -> list[KnowledgeArticle]:
    return list(session.scalars(select(KnowledgeArticle).where(KnowledgeArticle.is_published.is_(True)).order_by(KnowledgeArticle.category, KnowledgeArticle.sort_order, KnowledgeArticle.title)))


@router.get("/admin/knowledge", response_model=list[KnowledgeAdmin])
def list_knowledge(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*EDITOR_ROLES)),
) -> list[KnowledgeAdmin]:
    statement = select(KnowledgeArticle)
    if q and q.strip():
        value = f"%{q.strip()}%"
        statement = statement.where(or_(KnowledgeArticle.title.ilike(value), KnowledgeArticle.category.ilike(value), KnowledgeArticle.slug.ilike(value)))
    return [_response(article) for article in session.scalars(statement.order_by(KnowledgeArticle.category, KnowledgeArticle.sort_order, KnowledgeArticle.title).limit(limit).offset(offset))]


@router.post("/admin/knowledge", status_code=status.HTTP_201_CREATED, response_model=KnowledgeAdmin)
def create_knowledge(
    body: KnowledgeWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*EDITOR_ROLES)),
) -> KnowledgeAdmin:
    values = body.model_dump(mode="json")
    article = KnowledgeArticle(**{key: value for key, value in values.items()}, is_published=False, draft_data=values)
    session.add(article)
    session.add(AuditEvent(actor_uid=admin.uid, action="knowledge.created", entity_type="knowledge_article", entity_id=str(article.id), change_summary={"changed_fields": list(values)}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A knowledge article with this slug already exists") from error
    session.refresh(article)
    return _response(article)


@router.patch("/admin/knowledge/{article_id}", response_model=KnowledgeAdmin)
def update_knowledge(
    article_id: UUID,
    body: KnowledgePatch,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*EDITOR_ROLES)),
) -> KnowledgeAdmin:
    article = session.get(KnowledgeArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Knowledge article not found")
    values = _payload(article)
    patch = body.model_dump(exclude_unset=True, mode="json")
    values.update(patch)
    values = KnowledgeWrite.model_validate(values).model_dump(mode="json")
    article.draft_data = values
    if not article.is_published:
        for key, value in values.items():
            setattr(article, key, value)
    session.add(AuditEvent(actor_uid=admin.uid, action="knowledge.draft_saved", entity_type="knowledge_article", entity_id=str(article.id), change_summary={"changed_fields": list(patch)}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A knowledge article with this slug already exists") from error
    session.refresh(article)
    return _response(article)


@router.post("/admin/knowledge/{article_id}/publish", response_model=KnowledgeAdmin)
def publish_knowledge(
    article_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("content_editor", "admin", "super_admin")),
) -> KnowledgeAdmin:
    article = session.get(KnowledgeArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Knowledge article not found")
    values = KnowledgeWrite.model_validate(_payload(article)).model_dump(mode="json")
    if not values.get("source_reference"):
        raise HTTPException(status_code=422, detail="Add an approved source reference before publishing this answer")
    for key, value in values.items():
        setattr(article, key, value)
    article.draft_data = None
    article.is_published = True
    session.add(AuditEvent(actor_uid=admin.uid, action="knowledge.published", entity_type="knowledge_article", entity_id=str(article.id), change_summary={"published": True}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A knowledge article with this slug already exists") from error
    session.refresh(article)
    return _response(article)


@router.post("/admin/knowledge/{article_id}/unpublish", response_model=KnowledgeAdmin)
def unpublish_knowledge(
    article_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("admin", "super_admin")),
) -> KnowledgeAdmin:
    article = session.get(KnowledgeArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Knowledge article not found")
    article.is_published = False
    session.add(AuditEvent(actor_uid=admin.uid, action="knowledge.unpublished", entity_type="knowledge_article", entity_id=str(article.id), change_summary={"is_published": False}))
    session.commit()
    session.refresh(article)
    return _response(article)
