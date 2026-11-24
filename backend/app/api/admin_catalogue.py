from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.db.session import get_session
from app.models import AuditEvent, Product, ProductCategory
from app.schemas.cms import CategoryAdmin, CategoryPatch, CategoryWrite, ProductAdmin, ProductAdminPage, ProductPatch, ProductWrite

router = APIRouter(prefix="/admin/catalogue", tags=["admin catalogue"])
CONTENT_ROLES = ("content_editor", "admin", "super_admin")


def _audit(session: Session, admin: AdminIdentity, action: str, entity_type: str, entity_id: str, fields: list[str]) -> None:
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        change_summary={"changed_fields": fields},
    ))


def _category_payload(category: ProductCategory) -> dict[str, object]:
    if category.draft_data:
        return category.draft_data
    return {
        "slug": category.slug,
        "name": category.name,
        "description": category.description,
        "sort_order": category.sort_order,
        "image_url": category.image_url,
    }


def _category_response(category: ProductCategory) -> CategoryAdmin:
    draft = _category_payload(category)
    return CategoryAdmin(
        id=category.id,
        slug=str(draft["slug"]),
        name=str(draft["name"]),
        description=draft.get("description"),
        sort_order=int(draft.get("sort_order", 0)),
        image_url=str(draft["image_url"]) if draft.get("image_url") else None,
        wordpress_source_id=category.wordpress_source_id,
        is_published=category.is_published,
        has_draft=category.draft_data is not None,
    )


def _product_payload(product: Product) -> dict[str, object]:
    if product.draft_data:
        return product.draft_data
    return {
        "category_id": str(product.category_id),
        "slug": product.slug,
        "name": product.name,
        "model_code": product.model_code,
        "summary": product.summary,
        "description": product.description,
        "applications": product.applications or [],
        "features": product.features or [],
        "specifications": product.specifications or {},
        "image_url": product.image_url,
        "gallery_images": product.gallery_images or [],
        "price_minor": product.price_minor,
        "currency_code": product.currency_code or "INR",
        "currency_minor_unit": product.currency_minor_unit if product.currency_minor_unit is not None else 2,
        "currency_minor_unit": product.currency_minor_unit if product.currency_minor_unit is not None else 2,
        "stock_status": product.stock_status or "unknown",
        "stock_quantity": product.stock_quantity,
        "documents": product.documents or [],
        "source_reference": product.source_reference,
        "wordpress_source_id": product.wordpress_source_id,
        "wordpress_source_url": product.wordpress_source_url,
    }


def _product_response(product: Product) -> ProductAdmin:
    draft = _product_payload(product)
    return ProductAdmin(
        id=product.id,
        category_id=UUID(str(draft["category_id"])),
        slug=str(draft["slug"]),
        name=str(draft["name"]),
        model_code=draft.get("model_code"),
        summary=draft.get("summary"),
        description=draft.get("description"),
        applications=draft.get("applications") or [],
        features=draft.get("features") or [],
        specifications=draft.get("specifications") or {},
        image_url=str(draft["image_url"]) if draft.get("image_url") else None,
        gallery_images=draft.get("gallery_images") or [],
        price_minor=draft.get("price_minor"),
        currency_code=draft.get("currency_code") or "INR",
        currency_minor_unit=draft.get("currency_minor_unit", 2),
        stock_status=draft.get("stock_status") or "unknown",
        stock_quantity=draft.get("stock_quantity"),
        documents=draft.get("documents") or [],
        source_reference=draft.get("source_reference"),
        wordpress_source_id=draft.get("wordpress_source_id"),
        wordpress_source_url=draft.get("wordpress_source_url"),
        is_published=product.is_published,
        has_draft=product.draft_data is not None,
        updated_at=product.updated_at.isoformat(),
    )


@router.get("/categories", response_model=list[CategoryAdmin])
def admin_categories(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> list[CategoryAdmin]:
    statement = select(ProductCategory)
    if q and q.strip():
        value = f"%{q.strip()}%"
        statement = statement.where(or_(ProductCategory.name.ilike(value), ProductCategory.slug.ilike(value)))
    rows = session.scalars(statement.order_by(ProductCategory.sort_order, ProductCategory.name).limit(limit).offset(offset))
    return [_category_response(row) for row in rows]


@router.post("/categories", status_code=status.HTTP_201_CREATED, response_model=CategoryAdmin)
def create_category(
    body: CategoryWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CategoryAdmin:
    values = body.model_dump(mode="json")
    category = ProductCategory(
        slug=values["slug"], name=values["name"], description=values["description"],
        sort_order=values["sort_order"], image_url=values["image_url"], is_published=False,
        draft_data=values,
    )
    session.add(category)
    _audit(session, admin, "category.created", "product_category", str(category.id), list(values))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A category with this slug already exists") from error
    session.refresh(category)
    return _category_response(category)


@router.patch("/categories/{category_id}", response_model=CategoryAdmin)
def update_category(
    category_id: UUID,
    body: CategoryPatch,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CategoryAdmin:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This category is managed by WordPress; change it in WordPress and sync again")
    values = _category_payload(category)
    patch = body.model_dump(exclude_unset=True, mode="json")
    values.update(patch)
    validated = CategoryWrite.model_validate(values).model_dump(mode="json")
    category.draft_data = validated
    if not category.is_published:
        category.slug = validated["slug"]
        category.name = validated["name"]
        category.description = validated["description"]
        category.sort_order = validated["sort_order"]
        category.image_url = validated["image_url"]
    _audit(session, admin, "category.draft_saved", "product_category", str(category.id), list(patch))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A category with this slug already exists") from error
    session.refresh(category)
    return _category_response(category)


@router.post("/categories/{category_id}/publish", response_model=CategoryAdmin)
def publish_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> CategoryAdmin:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    values = CategoryWrite.model_validate(_category_payload(category)).model_dump(mode="json")
    category.slug = values["slug"]
    category.name = values["name"]
    category.description = values["description"]
    category.sort_order = values["sort_order"]
    category.image_url = values["image_url"]
    category.draft_data = None
    category.is_published = True
    _audit(session, admin, "category.published", "product_category", str(category.id), ["published"])
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A category with this slug already exists") from error
    session.refresh(category)
    return _category_response(category)


@router.post("/categories/{category_id}/unpublish", response_model=CategoryAdmin)
def unpublish_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> CategoryAdmin:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This category is managed by WordPress; change it there and sync again")
    category.is_published = False
    _audit(session, admin, "category.unpublished", "product_category", str(category.id), ["is_published"])
    session.commit()
    session.refresh(category)
    return _category_response(category)


@router.get("/products", response_model=ProductAdminPage)
def admin_products(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdminPage:
    statement = select(Product).join(Product.category)
    filters = []
    if category:
        filters.append(ProductCategory.slug == category)
    if q and q.strip():
        value = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(value), Product.model_code.ilike(value), Product.summary.ilike(value)))
    filtered = statement.where(*filters)
    total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = session.scalars(filtered.order_by(Product.updated_at.desc(), Product.name).limit(limit).offset(offset))
    return ProductAdminPage(items=[_product_response(row) for row in rows], total=total, limit=limit, offset=offset)


@router.post("/products", status_code=status.HTTP_201_CREATED, response_model=ProductAdmin)
def create_product(
    body: ProductWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    category = session.get(ProductCategory, body.category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Select an existing category")
    values = body.model_dump(mode="json")
    product = Product(
        category_id=body.category_id, slug=body.slug, name=body.name,
        model_code=body.model_code, summary=body.summary, is_published=False,
        draft_data=values,
    )
    session.add(product)
    _audit(session, admin, "product.created", "product", str(product.id), list(values))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug already exists") from error
    session.refresh(product)
    return _product_response(product)


@router.patch("/products/{product_id}", response_model=ProductAdmin)
def update_product(
    product_id: UUID,
    body: ProductPatch,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This product is managed by WooCommerce; change it there and sync again")
    values = _product_payload(product)
    patch = body.model_dump(exclude_unset=True, mode="json")
    values.update(patch)
    validated = ProductWrite.model_validate(values).model_dump(mode="json")
    if session.get(ProductCategory, UUID(validated["category_id"])) is None:
        raise HTTPException(status_code=422, detail="Select an existing category")
    product.draft_data = validated
    if not product.is_published:
        product.category_id = UUID(validated["category_id"])
        product.slug = validated["slug"]
        product.name = validated["name"]
        product.model_code = validated["model_code"]
        product.summary = validated["summary"]
    _audit(session, admin, "product.draft_saved", "product", str(product.id), list(patch))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug already exists") from error
    session.refresh(product)
    return _product_response(product)


@router.post("/products/{product_id}/publish", response_model=ProductAdmin)
def publish_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> ProductAdmin:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    values = ProductWrite.model_validate(_product_payload(product)).model_dump(mode="json")
    if not values.get("source_reference"):
        raise HTTPException(status_code=422, detail="Add a verified source reference before publishing this product")
    category = session.get(ProductCategory, UUID(values["category_id"]))
    if category is None or not category.is_published:
        raise HTTPException(status_code=409, detail="Publish the product category before publishing this product")
    product.category_id = UUID(values["category_id"])
    product.slug = values["slug"]
    product.name = values["name"]
    product.model_code = values["model_code"]
    product.summary = values["summary"]
    product.description = values["description"]
    product.applications = values["applications"]
    product.features = values["features"]
    product.specifications = values["specifications"]
    product.image_url = values["image_url"]
    product.gallery_images = values["gallery_images"]
    product.price_minor = values["price_minor"]
    product.currency_code = values["currency_code"]
    product.currency_minor_unit = values["currency_minor_unit"]
    product.stock_status = values["stock_status"]
    product.stock_quantity = values["stock_quantity"]
    product.documents = [document.model_dump(mode="json") if hasattr(document, "model_dump") else document for document in values["documents"]]
    product.wordpress_source_id = values["wordpress_source_id"]
    product.wordpress_source_url = values["wordpress_source_url"]
    product.source_reference = values["source_reference"]
    product.content_verified_at = datetime.now(timezone.utc)
    product.published_at = datetime.now(timezone.utc)
    product.is_published = True
    product.draft_data = None
    fields = list(values)
    _audit(session, admin, "product.published", "product", str(product.id), fields)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug already exists") from error
    session.refresh(product)
    return _product_response(product)


@router.post("/products/{product_id}/unpublish", response_model=ProductAdmin)
def unpublish_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> ProductAdmin:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This product is managed by WooCommerce; change it there and sync again")
    product.is_published = False
    _audit(session, admin, "product.unpublished", "product", str(product.id), ["is_published"])
    session.commit()
    session.refresh(product)
    return _product_response(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> None:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    _audit(session, admin, "product.deleted", "product", str(product.id), ["deleted"])
    session.delete(product)
    session.commit()


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> None:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    _audit(session, admin, "category.deleted", "product_category", str(category.id), ["deleted"])
    session.delete(category)
    session.commit()

