from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

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
from app.schemas.catalogue import CategoryPublic, ProductDocument, ProductPage, ProductPublic
from app.services.catalogue_documents import (
    CategoryCatalogueLookup,
    load_category_catalogue_lookup,
    resolve_product_documents_for_model,
)

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


def _public_product_response(product: Product, lookup: CategoryCatalogueLookup) -> ProductPublic:
    resolved_docs, catalog_pdf_url, _ = resolve_product_documents_for_model(product, lookup)
    return ProductPublic(
        id=product.id,
        slug=product.slug,
        name=product.name,
        model_code=product.model_code,
        summary=product.summary,
        description=product.description,
        applications=product.applications or [],
        features=product.features or [],
        specifications=product.specifications or {},
        image_url=product.image_url,
        gallery_images=product.gallery_images or [],
        price_minor=product.price_minor,
        currency_code=product.currency_code or "INR",
        currency_minor_unit=product.currency_minor_unit if product.currency_minor_unit is not None else 2,
        stock_status=product.stock_status or "unknown",
        stock_quantity=product.stock_quantity,
        documents=[ProductDocument.model_validate(doc) for doc in resolved_docs],
        catalog_pdf_url=catalog_pdf_url,
        category_id=product.category_id,
        category_ids=product.category_ids,
        updated_at=product.updated_at,
    )


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
    filters = [
        Product.is_published.is_(True),
        or_(Product.category.has(ProductCategory.is_published.is_(True)), Product.categories.any(ProductCategory.is_published.is_(True))),
    ]
    statement = select(Product).options(selectinload(Product.categories), selectinload(Product.category))
    if ids is not None:
        try:
            selected_ids = [UUID(value.strip()) for value in ids.split(",")]
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Product IDs must be valid UUIDs") from error
        if not selected_ids or len(selected_ids) > 12:
            raise HTTPException(status_code=422, detail="Choose between 1 and 12 product IDs")
        filters.append(Product.id.in_(selected_ids))
    if category:
        visible_category = and_(ProductCategory.slug == category, ProductCategory.is_published.is_(True))
        filters.append(or_(Product.category.has(visible_category), Product.categories.any(visible_category)))
    if q:
        search = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(search), Product.model_code.ilike(search), Product.summary.ilike(search), Product.description.ilike(search)))
    filtered = statement.where(*filters)
    total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    items = list(session.scalars(filtered.order_by(Product.name).limit(limit).offset(offset)))
    lookup = load_category_catalogue_lookup(session)
    return ProductPage(
        items=[_public_product_response(item, lookup) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/catalogue/products/{slug}", response_model=ProductPublic, tags=["catalogue"])
def get_product(slug: str, session: Session = Depends(get_session)) -> ProductPublic:
    require_database()
    statement = (
        select(Product)
        .options(selectinload(Product.categories), selectinload(Product.category))
        .where(
            Product.slug == slug,
            Product.is_published.is_(True),
            or_(Product.category.has(ProductCategory.is_published.is_(True)), Product.categories.any(ProductCategory.is_published.is_(True))),
        )
    )
    product = session.scalar(statement)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    lookup = load_category_catalogue_lookup(session)
    return _public_product_response(product, lookup)
