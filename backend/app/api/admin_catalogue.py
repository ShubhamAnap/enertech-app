from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.auth import AdminIdentity, require_admin_roles
from app.db.session import get_session
from app.models import (
    AppConfig,
    AuditEvent,
    ContactInquiry,
    CustomerProfile,
    CustomerRequest,
    Product,
    ProductCategory,
    ProductCategoryCatalogue,
)
from app.schemas.cms import (
    CatalogueSummaryAdmin,
    CategoryAdmin,
    CategoryBulkVisibilityWrite,
    CategoryCatalogueAdmin,
    CategoryCatalogueWrite,
    CategoryPatch,
    CategoryWrite,
    ProductAdmin,
    ProductAdminPage,
    ProductBulkCategoryWrite,
    ProductCategoryOverrideWrite,
    ProductPatch,
    ProductPdfOverrideWrite,
    ProductWrite,
)
from app.services.catalogue_documents import (
    CategoryCatalogueLookup,
    load_category_catalogue_lookup,
    load_category_product_counts,
    resolve_product_documents,
    resolve_product_documents_for_model,
)

router = APIRouter(prefix="/admin/catalogue", tags=["admin catalogue"])
CONTENT_ROLES = ("content_editor", "admin", "super_admin")


def _is_featured_in_home(session: Session, field: str, item_id: UUID) -> bool:
    home = session.scalar(select(AppConfig).where(AppConfig.key == "home"))
    if home is None:
        return False
    item_id_text = str(item_id)
    for payload in (home.draft_payload, home.published_payload):
        if payload is None:
            continue
        selected = payload.get(field)
        if isinstance(selected, list) and item_id_text in {str(value) for value in selected}:
            return True
    return False


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


def _category_response(
    category: ProductCategory,
    lookup: CategoryCatalogueLookup | None = None,
    product_count: int = 0,
) -> CategoryAdmin:
    draft = _category_payload(category)
    matched_catalogue = lookup.match_category(category) if lookup is not None else None
    return CategoryAdmin(
        id=category.id,
        slug=str(draft["slug"]),
        name=str(draft["name"]),
        description=draft.get("description"),
        sort_order=int(draft.get("sort_order", 0)),
        image_url=str(draft["image_url"]) if draft.get("image_url") else None,
        wordpress_source_id=category.wordpress_source_id,
        cms_locked=bool(category.cms_locked),
        product_count=product_count,
        is_published=category.is_published,
        has_draft=category.draft_data is not None,
        catalog_pdf_url=matched_catalogue.catalog_pdf_url if matched_catalogue else None,
        catalog_pdf_title=matched_catalogue.title if matched_catalogue else None,
        published_payload={
            "slug": category.slug,
            "name": category.name,
            "description": category.description,
            "sort_order": category.sort_order,
            "image_url": category.image_url,
        } if category.is_published else None,
    )


def _product_payload(product: Product) -> dict[str, object]:
    if product.draft_data:
        return product.draft_data
    return {
        "category_id": str(product.category_id),
        "category_ids": [str(value) for value in product.category_ids],
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
        "stock_status": product.stock_status or "unknown",
        "stock_quantity": product.stock_quantity,
        "documents": product.documents or [],
        "source_reference": product.source_reference,
        "wordpress_source_id": product.wordpress_source_id,
        "wordpress_source_url": product.wordpress_source_url,
    }


def _resolve_categories(session: Session, category_ids: list[UUID]) -> list[ProductCategory]:
    ordered_ids = list(dict.fromkeys(category_ids))
    categories_by_id = {
        category.id: category
        for category in session.scalars(select(ProductCategory).where(ProductCategory.id.in_(ordered_ids)))
    }
    if len(categories_by_id) != len(ordered_ids):
        raise HTTPException(status_code=422, detail="Select existing collections for this product")
    return [categories_by_id[category_id] for category_id in ordered_ids]


def _product_response(product: Product, lookup: CategoryCatalogueLookup | None = None) -> ProductAdmin:
    draft = _product_payload(product)
    cat_id = draft.get("category_id") or product.category_id
    if isinstance(cat_id, str):
        try:
            parsed_cat_id = UUID(cat_id)
        except (ValueError, TypeError):
            parsed_cat_id = product.category_id
    elif isinstance(cat_id, UUID):
        parsed_cat_id = cat_id
    else:
        parsed_cat_id = product.category_id
    if isinstance(draft.get("category_ids"), list):
        try:
            parsed_category_ids = list(dict.fromkeys(UUID(str(value)) for value in draft["category_ids"]))
        except (ValueError, TypeError):
            parsed_category_ids = [parsed_cat_id]
    elif product.draft_data is not None:
        parsed_category_ids = [parsed_cat_id]
    else:
        parsed_category_ids = product.category_ids

    raw_docs = draft.get("documents", product.documents or [])
    categories_for_doc: list[ProductCategory] = []
    if product.category is not None:
        categories_for_doc.append(product.category)
    for category in product.categories:
        if product.category is None or category.id != product.category.id:
            categories_for_doc.append(category)
    ordered_cat_ids = list(dict.fromkeys([parsed_cat_id, *parsed_category_ids]))
    resolved_docs, catalog_pdf_url, catalog_pdf_source = resolve_product_documents(
        raw_documents=raw_docs,
        category_ids=ordered_cat_ids,
        categories=categories_for_doc,
        lookup=lookup,
    )

    updated_str = product.updated_at.isoformat() if product.updated_at else datetime.now(timezone.utc).isoformat()

    return ProductAdmin(
        id=product.id,
        category_id=parsed_cat_id,
        category_ids=parsed_category_ids,
        slug=str(draft.get("slug") or product.slug),
        name=str(draft.get("name") or product.name),
        model_code=draft.get("model_code", product.model_code),
        summary=draft.get("summary", product.summary),
        description=draft.get("description", product.description),
        applications=draft.get("applications", product.applications or []),
        features=draft.get("features", product.features or []),
        specifications=draft.get("specifications", product.specifications or {}),
        image_url=str(draft["image_url"]) if draft.get("image_url") else (None if "image_url" in draft else product.image_url),
        gallery_images=draft.get("gallery_images", product.gallery_images or []),
        price_minor=draft.get("price_minor") if "price_minor" in draft else product.price_minor,
        currency_code=draft.get("currency_code") or product.currency_code or "INR",
        currency_minor_unit=draft.get("currency_minor_unit", product.currency_minor_unit if product.currency_minor_unit is not None else 2),
        stock_status=draft.get("stock_status", product.stock_status or "unknown"),
        stock_quantity=draft.get("stock_quantity", product.stock_quantity),
        documents=resolved_docs,
        catalog_pdf_url=catalog_pdf_url,
        catalog_pdf_source=catalog_pdf_source,
        source_reference=draft.get("source_reference", product.source_reference),
        wordpress_source_id=draft.get("wordpress_source_id") or product.wordpress_source_id,
        wordpress_source_url=draft.get("wordpress_source_url") or product.wordpress_source_url,
        category_override=bool(product.category_override),
        documents_override=bool(product.documents_override),
        is_published=product.is_published,
        has_draft=product.draft_data is not None,
        updated_at=updated_str,
        published_payload={
            "category_id": str(product.category_id),
            "category_ids": [str(value) for value in product.category_ids],
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
            "stock_status": product.stock_status or "unknown",
            "stock_quantity": product.stock_quantity,
            "documents": product.documents or [],
            "source_reference": product.source_reference,
            "wordpress_source_id": product.wordpress_source_id,
            "wordpress_source_url": product.wordpress_source_url,
        } if product.is_published else None,
    )


@router.get("/summary", response_model=CatalogueSummaryAdmin)
def admin_catalogue_summary(
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CatalogueSummaryAdmin:
    lookup = load_category_catalogue_lookup(session)
    counts = load_category_product_counts(session, published_only=False)
    products = list(session.scalars(select(Product).options(selectinload(Product.categories), selectinload(Product.category))))
    categories = list(session.scalars(select(ProductCategory)))
    open_service = session.scalar(
        select(func.count()).select_from(CustomerRequest).where(
            CustomerRequest.kind == "service",
            CustomerRequest.status.notin_(["resolved", "closed"]),
        )
    ) or 0
    open_quote = session.scalar(
        select(func.count()).select_from(CustomerRequest).where(
            CustomerRequest.kind == "quote",
            CustomerRequest.status.notin_(["quote_sent", "closed"]),
        )
    ) or 0
    open_inquiries = session.scalar(
        select(func.count()).select_from(ContactInquiry).where(
            ContactInquiry.status.notin_(["resolved", "closed"]),
        )
    ) or 0
    customers_total = session.scalar(select(func.count()).select_from(CustomerProfile)) or 0
    return CatalogueSummaryAdmin(
        products_total=len(products),
        products_published=sum(1 for item in products if item.is_published),
        products_missing_pdf=sum(1 for item in products if resolve_product_documents_for_model(item, lookup)[1] is None),
        products_category_overridden=sum(1 for item in products if item.category_override),
        products_pdf_overridden=sum(1 for item in products if item.documents_override),
        categories_total=len(categories),
        categories_published=sum(1 for cat in categories if cat.is_published),
        categories_hidden=sum(1 for cat in categories if not cat.is_published),
        categories_empty=sum(1 for cat in categories if counts.get(cat.id, 0) == 0),
        categories_missing_pdf=sum(1 for cat in categories if lookup.match_category(cat) is None),
        open_service_requests=int(open_service),
        open_quote_requests=int(open_quote),
        open_contact_inquiries=int(open_inquiries),
        customers_total=int(customers_total),
    )


@router.get("/categories", response_model=list[CategoryAdmin])
def admin_categories(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> list[CategoryAdmin]:
    statement = select(ProductCategory)
    if q and q.strip():
        value = f"%{q.strip()}%"
        statement = statement.where(or_(ProductCategory.name.ilike(value), ProductCategory.slug.ilike(value)))
    rows = list(session.scalars(statement.order_by(ProductCategory.sort_order, ProductCategory.name).limit(limit).offset(offset)))
    lookup = load_category_catalogue_lookup(session)
    counts = load_category_product_counts(session, published_only=False)
    return [_category_response(row, lookup, product_count=counts.get(row.id, 0)) for row in rows]


def _catalogue_mapping_response(mapping: ProductCategoryCatalogue) -> CategoryCatalogueAdmin:
    updated_str = mapping.updated_at.isoformat() if mapping.updated_at else datetime.now(timezone.utc).isoformat()
    return CategoryCatalogueAdmin(
        id=mapping.id,
        category_key=mapping.category_key,
        category_id=mapping.category_id,
        wordpress_category_id=mapping.wordpress_category_id,
        title=mapping.title,
        catalog_pdf_url=mapping.catalog_pdf_url,
        source=mapping.source,
        updated_at=updated_str,
    )


@router.get("/category-catalogues", response_model=list[CategoryCatalogueAdmin])
def list_category_catalogues(
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> list[CategoryCatalogueAdmin]:
    rows = session.scalars(select(ProductCategoryCatalogue).order_by(ProductCategoryCatalogue.category_key))
    return [_catalogue_mapping_response(row) for row in rows]


@router.put("/category-catalogues", response_model=CategoryCatalogueAdmin)
def upsert_category_catalogue(
    body: CategoryCatalogueWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CategoryCatalogueAdmin:
    normalized_key = body.category_key.strip().lower()
    category: ProductCategory | None = session.get(ProductCategory, body.category_id) if body.category_id else None
    if category is None:
        category = session.scalar(select(ProductCategory).where(ProductCategory.slug == normalized_key))
    if category is None and body.wordpress_category_id:
        category = session.scalar(
            select(ProductCategory).where(ProductCategory.wordpress_source_id == body.wordpress_category_id)
        )
    if category is not None:
        normalized_key = category.slug

    filters = [ProductCategoryCatalogue.category_key == normalized_key]
    if category is not None:
        filters.append(ProductCategoryCatalogue.category_id == category.id)
    existing = session.scalar(select(ProductCategoryCatalogue).where(or_(*filters)))
    if existing is None:
        existing = ProductCategoryCatalogue(
            category_key=normalized_key,
            category_id=category.id if category else body.category_id,
            wordpress_category_id=(category.wordpress_source_id if category else None) or body.wordpress_category_id,
            title=body.title.strip(),
            catalog_pdf_url=body.catalog_pdf_url.strip(),
            source="cms",
        )
        session.add(existing)
    else:
        existing.category_key = normalized_key
        existing.category_id = category.id if category else existing.category_id
        existing.wordpress_category_id = (
            (category.wordpress_source_id if category else None)
            or body.wordpress_category_id
            or existing.wordpress_category_id
        )
        existing.title = body.title.strip()
        existing.catalog_pdf_url = body.catalog_pdf_url.strip()
        existing.source = "cms"

    _audit(session, admin, "category_catalogue.upserted", "product_category_catalogue", normalized_key, ["catalog_pdf_url", "title"])
    session.commit()
    session.refresh(existing)
    return _catalogue_mapping_response(existing)


@router.delete("/category-catalogues/{catalogue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_catalogue(
    catalogue_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> None:
    mapping = session.get(ProductCategoryCatalogue, catalogue_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Category catalogue mapping not found")
    _audit(session, admin, "category_catalogue.deleted", "product_category_catalogue", mapping.category_key, ["deleted"])
    session.delete(mapping)
    session.commit()


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
    return _category_response(category, load_category_catalogue_lookup(session))


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
    patch = body.model_dump(exclude_unset=True, mode="json")
    requested_lock = patch.pop("cms_locked", None)

    if category.wordpress_source_id is not None:
        if "slug" in patch and patch["slug"] != category.slug:
            raise HTTPException(
                status_code=409,
                detail="WooCommerce collection slugs stay synced with WordPress; edit the display name or sort order instead",
            )
        values = dict(_category_payload(category))
        values.update({key: value for key, value in patch.items() if key != "slug"})
        validated = CategoryWrite.model_validate({**values, "slug": category.slug}).model_dump(mode="json")
        category.name = validated["name"]
        category.description = validated["description"]
        category.sort_order = validated["sort_order"]
        category.image_url = validated["image_url"]
        category.draft_data = None
        category.cms_locked = True if requested_lock is None else bool(requested_lock)
        _audit(session, admin, "category.cms_overridden", "product_category", str(category.id), list(patch))
        session.commit()
        session.refresh(category)
        counts = load_category_product_counts(session, published_only=False)
        return _category_response(category, load_category_catalogue_lookup(session), product_count=counts.get(category.id, 0))

    values = dict(_category_payload(category))
    values.update(patch)
    validated = CategoryWrite.model_validate(values).model_dump(mode="json")
    category.draft_data = validated
    if not category.is_published:
        category.slug = validated["slug"]
        category.name = validated["name"]
        category.description = validated["description"]
        category.sort_order = validated["sort_order"]
        category.image_url = validated["image_url"]
    if requested_lock is not None:
        category.cms_locked = bool(requested_lock)
    _audit(session, admin, "category.draft_saved", "product_category", str(category.id), list(patch))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A category with this slug already exists") from error
    session.refresh(category)
    counts = load_category_product_counts(session, published_only=False)
    return _category_response(category, load_category_catalogue_lookup(session), product_count=counts.get(category.id, 0))


@router.post("/categories/{category_id}/publish", response_model=CategoryAdmin)
def publish_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> CategoryAdmin:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.wordpress_source_id is not None:
        category.is_published = True
        category.cms_locked = True
        category.draft_data = None
        _audit(session, admin, "category.published", "product_category", str(category.id), ["is_published", "cms_locked"])
        session.commit()
        session.refresh(category)
        counts = load_category_product_counts(session, published_only=False)
        return _category_response(category, load_category_catalogue_lookup(session), product_count=counts.get(category.id, 0))
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
    counts = load_category_product_counts(session, published_only=False)
    return _category_response(category, load_category_catalogue_lookup(session), product_count=counts.get(category.id, 0))


@router.post("/categories/{category_id}/unpublish", response_model=CategoryAdmin)
def unpublish_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> CategoryAdmin:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    category.is_published = False
    if category.wordpress_source_id is not None:
        category.cms_locked = True
    _audit(session, admin, "category.unpublished", "product_category", str(category.id), ["is_published"])
    session.commit()
    session.refresh(category)
    counts = load_category_product_counts(session, published_only=False)
    return _category_response(category, load_category_catalogue_lookup(session), product_count=counts.get(category.id, 0))


@router.post("/categories/bulk-visibility", response_model=dict[str, int])
def bulk_update_category_visibility(
    body: CategoryBulkVisibilityWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> dict[str, int]:
    categories = list(session.scalars(select(ProductCategory).where(ProductCategory.id.in_(body.category_ids))))
    for category in categories:
        category.is_published = body.is_published
        if category.wordpress_source_id is not None:
            category.cms_locked = True
    _audit(
        session,
        admin,
        "category.bulk_visibility_updated",
        "product_category",
        ",".join(str(category.id) for category in categories[:10]),
        [f"is_published={body.is_published}", f"count={len(categories)}"],
    )
    session.commit()
    return {"updated": len(categories)}


@router.get("/products", response_model=ProductAdminPage)
def admin_products(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdminPage:
    statement = select(Product).options(selectinload(Product.categories), selectinload(Product.category))
    filters = []
    if category:
        filters.append(or_(Product.category.has(ProductCategory.slug == category), Product.categories.any(ProductCategory.slug == category)))
    if q and q.strip():
        value = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(value), Product.slug.ilike(value), Product.model_code.ilike(value), Product.summary.ilike(value), Product.description.ilike(value)))
    filtered = statement.where(*filters)
    total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = list(session.scalars(filtered.order_by(Product.updated_at.desc(), Product.name).limit(limit).offset(offset)))
    lookup = load_category_catalogue_lookup(session)
    return ProductAdminPage(items=[_product_response(row, lookup) for row in rows], total=total, limit=limit, offset=offset)


@router.post("/products", status_code=status.HTTP_201_CREATED, response_model=ProductAdmin)
def create_product(
    body: ProductWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    values = body.model_dump(mode="json")
    categories = _resolve_categories(session, body.category_ids)
    product = Product(
        category_id=body.category_id, slug=body.slug, name=body.name,
        model_code=body.model_code, summary=body.summary, is_published=False,
        draft_data=values,
    )
    product.categories = categories
    session.add(product)
    _audit(session, admin, "product.created", "product", str(product.id), list(values))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug already exists") from error
    session.refresh(product)
    return _product_response(product, load_category_catalogue_lookup(session))


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
    values = dict(_product_payload(product))
    patch = body.model_dump(exclude_unset=True, mode="json")
    values.update(patch)
    validated = ProductWrite.model_validate(values).model_dump(mode="json")
    categories = _resolve_categories(session, [UUID(value) for value in validated["category_ids"]])
    product.draft_data = validated
    if not product.is_published:
        product.category_id = UUID(validated["category_id"])
        product.categories = categories
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
    return _product_response(product, load_category_catalogue_lookup(session))


@router.post("/products/{product_id}/publish", response_model=ProductAdmin)
def publish_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> ProductAdmin:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This product is managed by WooCommerce; change it there and sync again")
    values = ProductWrite.model_validate(_product_payload(product)).model_dump(mode="json")
    if not values.get("source_reference"):
        raise HTTPException(status_code=422, detail="Add a verified source reference before publishing this product")
    categories = _resolve_categories(session, [UUID(value) for value in values["category_ids"]])
    if any(not category.is_published for category in categories):
        raise HTTPException(status_code=409, detail="Publish every selected collection before publishing this product")
    product.category_id = UUID(values["category_id"])
    product.categories = categories
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
    return _product_response(product, load_category_catalogue_lookup(session))


@router.put("/products/{product_id}/categories", response_model=ProductAdmin)
def override_product_categories(
    product_id: UUID,
    body: ProductCategoryOverrideWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    product = session.scalar(
        select(Product)
        .options(selectinload(Product.categories), selectinload(Product.category))
        .where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    categories = _resolve_categories(session, body.category_ids)
    product.category_id = body.category_id
    product.categories = categories
    if product.draft_data:
        draft = dict(product.draft_data)
        draft["category_id"] = str(body.category_id)
        draft["category_ids"] = [str(value) for value in body.category_ids]
        product.draft_data = draft
    product.category_override = product.wordpress_source_id is not None and not body.sync_with_wordpress
    _audit(
        session,
        admin,
        "product.categories_overridden",
        "product",
        str(product.id),
        ["category_id", "category_ids", f"category_override={product.category_override}"],
    )
    session.commit()
    session.refresh(product)
    return _product_response(product, load_category_catalogue_lookup(session))


@router.post("/products/bulk-category", response_model=dict[str, int])
def bulk_override_product_category(
    body: ProductBulkCategoryWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> dict[str, int]:
    primary_category = session.get(ProductCategory, body.category_id)
    if primary_category is None:
        raise HTTPException(status_code=422, detail="Select an existing collection for the bulk update")
    products = list(
        session.scalars(
            select(Product)
            .options(selectinload(Product.categories), selectinload(Product.category))
            .where(Product.id.in_(body.product_ids))
        )
    )
    for product in products:
        product.category_id = primary_category.id
        if body.keep_secondary_categories:
            existing = [cat for cat in product.categories if cat.id != primary_category.id]
            product.categories = [primary_category, *existing]
        else:
            product.categories = [primary_category]
        if product.draft_data:
            draft = dict(product.draft_data)
            draft["category_id"] = str(primary_category.id)
            draft["category_ids"] = [str(cat.id) for cat in product.categories]
            product.draft_data = draft
        if product.wordpress_source_id is not None:
            product.category_override = True
    _audit(
        session,
        admin,
        "product.bulk_category_overridden",
        "product",
        str(primary_category.id),
        [f"category_id={primary_category.id}", f"count={len(products)}"],
    )
    session.commit()
    return {"updated": len(products)}


@router.put("/products/{product_id}/pdf", response_model=ProductAdmin)
def override_product_pdf(
    product_id: UUID,
    body: ProductPdfOverrideWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    product = session.scalar(
        select(Product)
        .options(selectinload(Product.categories), selectinload(Product.category))
        .where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    clean_doc = {"title": body.title.strip(), "url": body.url.strip()}
    product.documents = [clean_doc]
    if product.draft_data:
        draft = dict(product.draft_data)
        draft["documents"] = [clean_doc]
        product.draft_data = draft
    if product.wordpress_source_id is not None:
        product.documents_override = True
    _audit(session, admin, "product.pdf_overridden", "product", str(product.id), ["documents", "documents_override"])
    session.commit()
    session.refresh(product)
    return _product_response(product, load_category_catalogue_lookup(session))


@router.delete("/products/{product_id}/pdf", response_model=ProductAdmin)
def clear_product_pdf_override(
    product_id: UUID,
    sync_with_wordpress: bool = Query(default=False),
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdmin:
    product = session.scalar(
        select(Product)
        .options(selectinload(Product.categories), selectinload(Product.category))
        .where(Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    product.documents = []
    if product.draft_data:
        draft = dict(product.draft_data)
        draft["documents"] = []
        product.draft_data = draft
    product.documents_override = product.wordpress_source_id is not None and not sync_with_wordpress
    _audit(
        session,
        admin,
        "product.pdf_cleared",
        "product",
        str(product.id),
        ["documents", f"documents_override={product.documents_override}"],
    )
    session.commit()
    session.refresh(product)
    return _product_response(product, load_category_catalogue_lookup(session))


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
    return _product_response(product, load_category_catalogue_lookup(session))


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> None:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This product is managed by WooCommerce; remove it there and sync again")
    if _is_featured_in_home(session, "featured_product_ids", product.id):
        raise HTTPException(status_code=409, detail="Remove this product from Home featured products before deleting it")
    _audit(session, admin, "product.deleted", "product", str(product.id), ["deleted"])
    session.delete(product)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This product is referenced by other catalogue content and cannot be deleted") from error


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin", "content_editor")),
) -> None:
    category = session.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.wordpress_source_id is not None:
        raise HTTPException(status_code=409, detail="This category is managed by WooCommerce; remove it there and sync again")
    product_count = session.scalar(select(func.count()).select_from(Product).where(or_(Product.category_id == category.id, Product.categories.any(ProductCategory.id == category.id)))) or 0
    if product_count:
        raise HTTPException(status_code=409, detail="Move or delete the products in this collection before deleting it")
    if _is_featured_in_home(session, "featured_category_ids", category.id):
        raise HTTPException(status_code=409, detail="Remove this collection from Home featured collections before deleting it")
    _audit(session, admin, "category.deleted", "product_category", str(category.id), ["deleted"])
    session.delete(category)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This collection is referenced by catalogue content and cannot be deleted") from error

