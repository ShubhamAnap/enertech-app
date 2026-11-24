from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.admin_catalogue import router as admin_catalogue_router
from app.api.admin_operations import router as admin_operations_router
from app.api.customer_requests import router as customer_requests_router
from app.api.customer_profiles import router as customer_profiles_router
from app.api.knowledge import router as knowledge_router
from app.api.media import router as media_router
from app.api.app_content import router as app_content_router
from app.api.wordpress import router as wordpress_router
from app.core.auth import AdminIdentity, get_current_admin
from app.core.config import get_settings
from app.db.session import engine, get_session
from app.models import Product, ProductCategory
from app.schemas.catalogue import CategoryPublic, ProductPage, ProductPublic

router = APIRouter()
router.include_router(admin_catalogue_router)
router.include_router(admin_operations_router)
router.include_router(customer_requests_router)
router.include_router(customer_profiles_router)
router.include_router(knowledge_router)
router.include_router(media_router)
router.include_router(app_content_router)
router.include_router(wordpress_router)


@router.get("/admin/session", tags=["admin authentication"])
def admin_session(admin: AdminIdentity = Depends(get_current_admin)) -> dict[str, str | None]:
    return {"uid": admin.uid, "email": admin.email, "display_name": admin.name, "role": admin.role}


def require_database() -> None:
    if engine is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Catalogue service is not configured")


@router.get("/health/ready", tags=["health"])
def readiness(session: Session = Depends(get_session)) -> dict[str, str]:
    settings = get_settings()
    if settings.app_env.lower() == "production" and not (
        settings.firebase_project_id.strip() and settings.firebase_service_account_json.strip()
    ):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Firebase Authentication is not configured")
    session.execute(select(1))
    return {"status": "ready"}


@router.get("/catalogue/categories", response_model=list[CategoryPublic], tags=["catalogue"])
def list_categories(session: Session = Depends(get_session)) -> list[ProductCategory]:
    require_database()
    statement = select(ProductCategory).where(ProductCategory.is_published.is_(True)).order_by(ProductCategory.sort_order, ProductCategory.name)
    return list(session.scalars(statement))


@router.get("/catalogue/products", response_model=ProductPage, tags=["catalogue"])
def list_products(
    session: Session = Depends(get_session),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    category: str | None = Query(default=None, min_length=1, max_length=120),
    ids: str | None = Query(default=None, min_length=36, max_length=443),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ProductPage:
    require_database()
    filters = [Product.is_published.is_(True), ProductCategory.is_published.is_(True)]
    statement = select(Product).join(Product.category)
    if ids is not None:
        try:
            selected_ids = [UUID(value.strip()) for value in ids.split(",")]
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Product IDs must be valid UUIDs") from error
        if not selected_ids or len(selected_ids) > 12:
            raise HTTPException(status_code=422, detail="Choose between 1 and 12 product IDs")
        filters.append(Product.id.in_(selected_ids))
    if category:
        filters.append(ProductCategory.slug == category)
    if q:
        search = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(search), Product.model_code.ilike(search), Product.summary.ilike(search), Product.description.ilike(search)))
    filtered = statement.where(*filters)
    total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    items = list(session.scalars(filtered.order_by(Product.name).limit(limit).offset(offset)))
    return ProductPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/catalogue/products/{slug}", response_model=ProductPublic, tags=["catalogue"])
def get_product(slug: str, session: Session = Depends(get_session)) -> Product:
    require_database()
    statement = (
        select(Product)
        .join(Product.category)
        .where(Product.slug == slug, Product.is_published.is_(True), ProductCategory.is_published.is_(True))
    )
    product = session.scalar(statement)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
