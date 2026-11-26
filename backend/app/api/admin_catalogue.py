from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, not_, or_, select
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
    CollectionProductsWrite,
    ProductAdmin,
    ProductAdminPage,
    ProductBulkCategoryWrite,
    ProductCategoryOverrideWrite,
    ProductPatch,
    ProductPdfOverrideWrite,
    ProductWrite,
)
from app.services.catalogue_membership import staging_tag
from app.services.catalogue_documents import (
    normalize_pdf_documents,
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
        is_app_collection=bool(category.is_app_collection),
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
        for category in session.scalars(select(ProductCategory).where(ProductCategory.id.in_(ordered_ids), ProductCategory.is_app_collection.is_(True)))
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
    seen_doc_cat_ids: set[UUID] = set()
    if product.category is not None:
        categories_for_doc.append(product.category)
        seen_doc_cat_ids.add(product.category.id)
    for category in product.categories:
        if category.id not in seen_doc_cat_ids:
            categories_for_doc.append(category)
            seen_doc_cat_ids.add(category.id)
    if lookup is not None:
        for cid in [parsed_cat_id, *parsed_category_ids]:
            if cid not in seen_doc_cat_ids and cid in lookup.categories_by_id:
                categories_for_doc.append(lookup.categories_by_id[cid])
                seen_doc_cat_ids.add(cid)

    app_collection_ids = [cat.id for cat in categories_for_doc if cat.is_app_collection]
    wordpress_tag_ids = [cat.id for cat in categories_for_doc if not cat.is_app_collection]

    ordered_cat_ids = list(dict.fromkeys([parsed_cat_id, *parsed_category_ids]))
    resolved_docs, catalog_pdf_url, catalog_pdf_source = resolve_product_documents(
        raw_documents=raw_docs,
        category_ids=ordered_cat_ids,
        categories=categories_for_doc,
        lookup=lookup,
        require_published_collections=False,
        app_collections_only=True,
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
        own_documents=normalize_pdf_documents(raw_docs),
        app_collection_ids=app_collection_ids,
        wordpress_tag_ids=wordpress_tag_ids,
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
    app_collections = [cat for cat in categories if cat.is_app_collection]
    wp_tags = [cat for cat in categories if not cat.is_app_collection]

    def _has_app_collection(item: Product) -> bool:
        if item.category is not None and item.category.is_app_collection:
            return True
        return any(cat.is_app_collection for cat in item.categories)

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
        products_published=sum(1 for item in products if item.is_published and any(cat.is_app_collection and cat.is_published for cat in [item.category, *item.categories])),
        products_missing_pdf=sum(
            1
            for item in products
            if resolve_product_documents_for_model(
                item,
                lookup,
                require_published_collections=False,
                app_collections_only=True,
            )[1] is None
        ),
        products_category_overridden=sum(1 for item in products if item.category_override),
        products_pdf_overridden=sum(1 for item in products if item.documents_override),
        products_unassigned=sum(1 for item in products if not _has_app_collection(item)),
        categories_total=len(app_collections),
        categories_published=sum(1 for cat in app_collections if cat.is_published),
        categories_hidden=sum(1 for cat in app_collections if not cat.is_published),
        categories_empty=sum(1 for cat in app_collections if counts.get(cat.id, 0) == 0),
        categories_missing_pdf=sum(1 for cat in app_collections if lookup.match_category(cat) is None),
        wordpress_tags_total=len(wp_tags),
        open_service_requests=int(open_service),
        open_quote_requests=int(open_quote),
        open_contact_inquiries=int(open_inquiries),
        customers_total=int(customers_total),
    )


@router.get("/categories", response_model=list[CategoryAdmin])
def admin_categories(
    q: str | None = Query(default=None, max_length=120),
    kind: Literal["app_collection", "wp_tag", "all"] = Query(default="app_collection"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> list[CategoryAdmin]:
    statement = select(ProductCategory)
    if kind == "app_collection":
        statement = statement.where(ProductCategory.is_app_collection.is_(True))
    elif kind == "wp_tag":
        statement = statement.where(ProductCategory.is_app_collection.is_(False))
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
    if category is None or not category.is_app_collection:
        raise HTTPException(status_code=422, detail="Choose a CMS app collection for this brochure")
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


def _sync_collection_catalogue_pdf(
    session: Session,
    *,
    category: ProductCategory,
    pdf_url: str | None,
    pdf_title: str | None = None,
) -> None:
    existing = session.scalar(
        select(ProductCategoryCatalogue).where(
            or_(
                ProductCategoryCatalogue.category_id == category.id,
                ProductCategoryCatalogue.category_key == category.slug,
            )
        )
    )
    if pdf_url is None:
        if existing is not None:
            session.delete(existing)
        return
    clean_title = (pdf_title or f"{category.name} Catalogue PDF").strip()[:180] or "Collection catalogue PDF"
    clean_url = pdf_url.strip()[:1000]
    if existing is None:
        session.add(
            ProductCategoryCatalogue(
                category_key=category.slug,
                category_id=category.id,
                wordpress_category_id=category.wordpress_source_id,
                title=clean_title,
                catalog_pdf_url=clean_url,
                source="cms",
            )
        )
        return
    existing.category_key = category.slug
    existing.category_id = category.id
    existing.wordpress_category_id = category.wordpress_source_id or existing.wordpress_category_id
    existing.title = clean_title
    existing.catalog_pdf_url = clean_url
    existing.source = "cms"


@router.post("/categories", status_code=status.HTTP_201_CREATED, response_model=CategoryAdmin)
def create_category(
    body: CategoryWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CategoryAdmin:
    values = body.model_dump(mode="json")
    pdf_url = values.pop("catalog_pdf_url", None)
    pdf_title = values.pop("catalog_pdf_title", None)
    category = ProductCategory(
        slug=values["slug"],
        name=values["name"],
        description=values["description"],
        sort_order=values["sort_order"],
        image_url=values["image_url"],
        is_app_collection=True,
        is_published=False,
        draft_data=values,
    )
    session.add(category)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A category with this slug already exists") from error
    if pdf_url:
        _sync_collection_catalogue_pdf(session, category=category, pdf_url=pdf_url, pdf_title=pdf_title)
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
    has_pdf_url_patch = "catalog_pdf_url" in patch
    patched_pdf_url = patch.pop("catalog_pdf_url", None)
    has_pdf_title_patch = "catalog_pdf_title" in patch
    patched_pdf_title = patch.pop("catalog_pdf_title", None)

    if not category.is_app_collection:
        raise HTTPException(status_code=409, detail="WordPress source tags are read-only")

    values = dict(_category_payload(category))
    values.update(patch)
    validated = CategoryWrite.model_validate(values).model_dump(mode="json")
    draft_values = {k: validated[k] for k in ("slug", "name", "description", "sort_order", "image_url")}
    category.draft_data = draft_values
    if not category.is_published:
        category.slug = draft_values["slug"]
        category.name = draft_values["name"]
        category.description = draft_values["description"]
        category.sort_order = draft_values["sort_order"]
        category.image_url = draft_values["image_url"]
    if has_pdf_url_patch:
        _sync_collection_catalogue_pdf(session, category=category, pdf_url=patched_pdf_url, pdf_title=patched_pdf_title)
    elif has_pdf_title_patch and patched_pdf_title:
        existing_mapping = load_category_catalogue_lookup(session).match_category(category)
        if existing_mapping is not None:
            existing_mapping.title = patched_pdf_title.strip()[:180]
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
    if not category.is_app_collection:
        raise HTTPException(status_code=409, detail="WordPress source tags cannot be published")
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
    if not category.is_app_collection:
        raise HTTPException(status_code=409, detail="WordPress source tags are read-only")
    category.is_published = False
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
    if any(not category.is_app_collection for category in categories):
        raise HTTPException(status_code=409, detail="WordPress source tags are read-only")
    for category in categories:
        category.is_published = body.is_published
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


@router.get("/categories/{category_id}/products")
def collection_product_options(
    category_id: UUID,
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> dict:
    collection = session.get(ProductCategory, category_id)
    if collection is None or not collection.is_app_collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    products = session.scalars(select(Product).options(selectinload(Product.category), selectinload(Product.categories)).order_by(Product.name, Product.id))
    rows = []
    for product in products:
        categories = set([product.category, *product.categories])
        rows.append({
            "id": product.id, "name": product.name, "sku": product.model_code,
            "checked": collection in categories,
            "assigned": any(cat.is_app_collection for cat in categories),
            "tag_ids": [cat.id for cat in categories if not cat.is_app_collection],
        })
    tags = session.scalars(select(ProductCategory).where(ProductCategory.is_app_collection.is_(False)).order_by(ProductCategory.name))
    return {"products": rows, "tags": [{"id": tag.id, "name": tag.name} for tag in tags]}


@router.put("/categories/{category_id}/products", response_model=CategoryAdmin)
def assign_collection_products(
    category_id: UUID,
    body: CollectionProductsWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> CategoryAdmin:
    collection = session.get(ProductCategory, category_id, with_for_update=True)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not collection.is_app_collection:
        raise HTTPException(
            status_code=409,
            detail="Only CMS app collections can be curated with products; WordPress tags remain read-only reference filters",
        )

    target_ids = set(body.product_ids)
    member = or_(Product.category_id == collection.id, Product.categories.any(ProductCategory.id == collection.id))
    products = list(session.scalars(
        select(Product).where(or_(member, Product.id.in_(target_ids)))
        .options(selectinload(Product.categories), selectinload(Product.category))
        .order_by(Product.id).with_for_update()
    ))
    if target_ids.difference(product.id for product in products):
        raise HTTPException(status_code=422, detail="One or more selected products could not be found")
    current_ids = {product.id for product in products if product.category_id == collection.id or collection in product.categories}
    if body.previous_product_ids is not None and current_ids != set(body.previous_product_ids):
        raise HTTPException(status_code=409, detail="Collection membership changed. Reopen Assign Products to refresh.")
    for product in products:
        if (product.id in current_ids) == (product.id in target_ids):
            continue
        others = list(dict.fromkeys(cat for cat in [product.category, *product.categories] if cat.id != collection.id))
        if product.id in target_ids:
            product.categories = [*others, collection]
            if not product.category.is_app_collection:
                product.category_id = collection.id
        else:
            if not others:
                others.append(staging_tag(session))
            product.categories = others
            if product.category_id == collection.id:
                product.category_id = next((cat.id for cat in others if cat.is_app_collection), others[0].id)
        if product.wordpress_source_id is not None:
            product.category_override = any(cat.is_app_collection for cat in product.categories)
        if product.draft_data:
            product.draft_data = {**product.draft_data, "category_id": str(product.category_id),
                                  "category_ids": [str(cat.id) for cat in product.categories]}

    _audit(
        session,
        admin,
        "collection.products_assigned",
        "product_category",
        str(collection.id),
        [f"assigned_count={len(target_ids)}"],
    )
    session.commit()
    session.refresh(collection)
    counts = load_category_product_counts(session, published_only=False)
    return _category_response(collection, load_category_catalogue_lookup(session), product_count=counts.get(collection.id, 0))


@router.get("/products", response_model=ProductAdminPage)
def admin_products(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=120),
    category_id: UUID | None = Query(default=None),
    assignment: Literal["all", "assigned", "unassigned"] = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles(*CONTENT_ROLES)),
) -> ProductAdminPage:
    statement = select(Product).options(selectinload(Product.categories), selectinload(Product.category))
    filters = []
    if assignment == "assigned":
        filters.append(
            or_(
                Product.category.has(ProductCategory.is_app_collection.is_(True)),
                Product.categories.any(ProductCategory.is_app_collection.is_(True)),
            )
        )
    elif assignment == "unassigned":
        filters.append(
            and_(
                not_(Product.category.has(ProductCategory.is_app_collection.is_(True))),
                not_(Product.categories.any(ProductCategory.is_app_collection.is_(True))),
            )
        )
    if category_id is not None:
        filters.append(or_(Product.category_id == category_id, Product.categories.any(ProductCategory.id == category_id)))
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
    selected = _resolve_categories(session, body.category_ids)
    selected_ids = {cat.id for cat in selected}
    preserved_wp_tags = list(dict.fromkeys(cat for cat in [product.category, *product.categories] if not cat.is_app_collection and cat.id not in selected_ids))
    product.category_id = body.category_id
    product.categories = [*selected, *preserved_wp_tags]
    if product.draft_data:
        draft = dict(product.draft_data)
        draft["category_id"] = str(body.category_id)
        draft["category_ids"] = [str(cat.id) for cat in product.categories]
        product.draft_data = draft
    product.category_override = product.wordpress_source_id is not None
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
    if primary_category is None or not primary_category.is_app_collection:
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
            wp_tags = [cat for cat in product.categories if not cat.is_app_collection and cat.id != primary_category.id]
            product.categories = [primary_category, *wp_tags]
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
    if not category.is_app_collection:
        raise HTTPException(status_code=409, detail="WordPress source tags are read-only")
    product_count = session.scalar(select(func.count()).select_from(Product).where(or_(Product.category_id == category.id, Product.categories.any(ProductCategory.id == category.id)))) or 0
    if product_count:
        raise HTTPException(status_code=409, detail="Move or delete the products in this collection before deleting it")
    if _is_featured_in_home(session, "featured_category_ids", category.id) or _is_featured_in_home(session, "featured_product_category_ids", category.id):
        raise HTTPException(status_code=409, detail="Remove this collection from Home featured collections before deleting it")
    for mapping in session.scalars(select(ProductCategoryCatalogue).where(ProductCategoryCatalogue.category_id == category.id)):
        session.delete(mapping)
    _audit(session, admin, "category.deleted", "product_category", str(category.id), ["deleted"])
    session.delete(category)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This collection is referenced by catalogue content and cannot be deleted") from error

