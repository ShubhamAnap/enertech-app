from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html.parser import HTMLParser
import json
import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AuditEvent, Product, ProductCategory

router = APIRouter(prefix="/admin/integrations/wordpress", tags=["wordpress integration"])
logger = logging.getLogger(__name__)
ROLES = ("content_editor", "admin", "super_admin")


class WordPressImport(BaseModel):
    source_id: str = Field(min_length=1, max_length=160)
    category_id: UUID


class _TextOnly(HTMLParser):
    _BLOCK_TAGS = {"address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "li", "ol", "p", "section", "table", "td", "th", "tr", "ul"}

    def __init__(self, *, preserve_blocks: bool = False) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.preserve_blocks = preserve_blocks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.preserve_blocks and tag in self._BLOCK_TAGS:
            self.parts.append("\n• " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if self.preserve_blocks and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _field(record: dict[str, Any], path: str, default: Any = None) -> Any:
    value: Any = record
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdecimal():
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            return default
    return default if value is None else value


def _plain(value: Any, limit: int = 500, *, preserve_blocks: bool = False) -> str:
    parser = _TextOnly(preserve_blocks=preserve_blocks)
    parser.feed(str(value or ""))
    if preserve_blocks:
        lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
        return "\n".join(line for line in lines if line)[:limit]
    return " ".join(" ".join(parser.parts).split())[:limit]


def _string_list(value: Any, limit: int = 32) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("options", item.get("name", item.get("value", "")))
        values = item if isinstance(item, list) else [item]
        for entry in values:
            text = _plain(entry, 180)
            if text:
                result.append(text)
            if len(result) >= limit:
                return result
    return result


def _image_url(value: Any) -> str | None:
    candidate = value.get("url", value.get("src")) if isinstance(value, dict) else value
    if not isinstance(candidate, str):
        return None
    candidate = candidate.strip()
    return candidate if candidate.startswith("https://") else None


def _specifications(value: Any) -> dict[str, str | list[str]]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = ((str(item.get("name", "")), item.get("options", item.get("value", ""))) for item in value if isinstance(item, dict))
    else:
        return {}
    result: dict[str, str | list[str]] = {}
    for key, raw in items:
        label = _plain(key, 80)
        value_text = _string_list(raw, 12) if isinstance(raw, list) else _plain(raw, 500)
        if label and value_text:
            result[label] = value_text
        if len(result) >= 60:
            break
    return result


def _wordpress_client() -> tuple[httpx.Client, str, Any]:
    settings = get_settings()
    base = settings.wordpress_api_base_url.rstrip("/")
    path = settings.wordpress_products_path.strip("/")
    if not base or not path:
        raise HTTPException(status_code=503, detail="Set WORDPRESS_API_BASE_URL and WORDPRESS_PRODUCTS_PATH in backend/.env")
    if not base.startswith("https://") and settings.app_env != "local":
        raise HTTPException(status_code=503, detail="WordPress must use HTTPS outside local development")
    auth = ((settings.wordpress_consumer_key, settings.wordpress_consumer_secret)
            if settings.wordpress_consumer_key and settings.wordpress_consumer_secret
            else (settings.wordpress_username, settings.wordpress_application_password)
            if settings.wordpress_username and settings.wordpress_application_password else None)
    client = httpx.Client(timeout=15, follow_redirects=False, auth=auth)
    return client, f"{base}/{path}", settings


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        text = response.text
        start_arr = text.find("[")
        start_obj = text.find("{")
        if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
            end_arr = text.rfind("]")
            if end_arr != -1:
                return json.loads(text[start_arr:end_arr + 1])
        elif start_obj != -1:
            end_obj = text.rfind("}")
            if end_obj != -1:
                return json.loads(text[start_obj:end_obj + 1])
        raise


def _fetch(limit: int, page: int = 1) -> tuple[list[dict[str, Any]], Any]:
    client, url, settings = _wordpress_client()
    try:
        response = client.get(url, params={"per_page": limit, "page": page, "status": "publish"}, headers={"Accept": "application/json"})
        if response.status_code in (401, 403):
            raise HTTPException(status_code=502, detail="WordPress rejected the configured REST API credentials")
        if response.status_code == 404:
            raise HTTPException(status_code=502, detail="WordPress product REST route was not found; check WORDPRESS_PRODUCTS_PATH")
        response.raise_for_status()
        payload = _safe_json(response)
        if not isinstance(payload, list):
            raise HTTPException(status_code=502, detail="WordPress returned an unexpected product response")
        return [item for item in payload if isinstance(item, dict)], settings
    except httpx.TimeoutException as error:
        raise HTTPException(status_code=504, detail="WordPress did not respond before the connection timed out") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Could not fetch products from WordPress") from error
    finally:
        client.close()


def _configured_rest_url(path: str) -> str:
    base = get_settings().wordpress_api_base_url.rstrip("/")
    if not base or not path.strip():
        raise HTTPException(status_code=503, detail="Set the WordPress REST URL and WooCommerce product routes in the API environment")
    if not base.startswith("https://") and get_settings().app_env != "local":
        raise HTTPException(status_code=503, detail="WordPress must use HTTPS outside local development")
    return f"{base}/{path.strip('/')}"


def _fetch_all(path: str, *, authenticated: bool, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    auth = (settings.wordpress_consumer_key, settings.wordpress_consumer_secret) if authenticated else None
    if authenticated and not all(auth or ()):
        raise HTTPException(status_code=503, detail="Set WORDPRESS_CONSUMER_KEY and WORDPRESS_CONSUMER_SECRET in the API environment")
    rows: list[dict[str, Any]] = []
    url = _configured_rest_url(path)
    with httpx.Client(timeout=25, follow_redirects=False, auth=auth) as client:
        for page in range(1, 101):
            params = {"per_page": 100, "page": page, **(extra_params or {})}
            try:
                response = client.get(url, params=params, headers={"Accept": "application/json"})
            except httpx.TimeoutException as error:
                raise HTTPException(status_code=504, detail="WordPress did not respond before the sync timed out") from error
            except httpx.HTTPError as error:
                raise HTTPException(status_code=502, detail="Could not connect to the configured WordPress REST endpoint") from error
            if response.status_code in (401, 403):
                raise HTTPException(status_code=502, detail="WordPress rejected the WooCommerce REST credentials or endpoint access")
            if response.status_code == 404:
                raise HTTPException(status_code=502, detail=f"WordPress REST route not found: {path}")
            try:
                response.raise_for_status()
                payload = _safe_json(response)
            except (httpx.HTTPError, ValueError) as error:
                raise HTTPException(status_code=502, detail=f"WordPress returned an invalid response from {path}") from error
            if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
                raise HTTPException(status_code=502, detail=f"WordPress returned an unexpected response from {path}")
            rows.extend(payload)
            try:
                total_pages = int(response.headers.get("X-WP-TotalPages", "0"))
            except ValueError:
                total_pages = 0
            if total_pages and page >= total_pages:
                return rows
            if not payload or len(payload) < 100:
                return rows
    raise HTTPException(status_code=413, detail="WordPress sync exceeded 10,000 records; narrow the product scope before syncing")


def _minor_units(value: Any, digits: int, *, already_minor: bool = False) -> int | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            return None
        if already_minor and amount == amount.to_integral_value():
            return int(amount)
        factor = Decimal(10) ** max(0, min(digits, 4))
        return int((amount * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_currency(value: Any) -> str:
    value = str(value or "INR").upper()
    return value if len(value) == 3 and value.isalpha() else "INR"


def _https_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    return value[:1000]


def _documents(product: dict[str, Any], media: list[dict[str, Any]]) -> list[dict[str, str]]:
    source_id = str(product.get("id", ""))
    found: dict[str, str] = {}
    downloads = product.get("downloads")
    if isinstance(downloads, list):
        for item in downloads:
            if not isinstance(item, dict):
                continue
            url = _https_url(item.get("file"))
            if url and url.lower().split("?", 1)[0].endswith(".pdf"):
                found[url] = _plain(item.get("name") or "Product brochure", 180) or "Product brochure"
    for item in media:
        if str(item.get("post")) != source_id:
            continue
        mime = str(item.get("mime_type") or "")
        url = _https_url(item.get("source_url"))
        if mime == "application/pdf" and url:
            title = _plain(_field(item, "title.rendered", "Product document"), 180)
            found[url] = title or "Product document"
    return [{"title": title, "url": url} for url, title in list(found.items())[:24]]


def _slug_for_product(session: Session, slug: str, source_id: str, existing: Product | None) -> str:
    base = slug or f"wordpress-product-{source_id}"
    candidate = base[:180]
    conflict = session.scalar(select(Product).where(Product.slug == candidate))
    if conflict is None or (existing is not None and conflict.id == existing.id):
        return candidate
    suffix = f"-wp-{source_id}"
    return f"{base[:180-len(suffix)]}{suffix}"


@router.get("/status")
def wordpress_status(_admin: AdminIdentity = Depends(require_admin_roles(*ROLES))) -> dict[str, Any]:
    settings = get_settings()
    credentials_ready = bool(settings.wordpress_consumer_key and settings.wordpress_consumer_secret)
    configured = bool(settings.wordpress_api_base_url and settings.wordpress_products_path and settings.wordpress_categories_path and settings.wordpress_store_products_path)
    return {
        "configured": configured,
        "authenticated": credentials_ready,
        "documents_configured": bool(settings.wordpress_documents_path),
        "site": settings.wordpress_api_base_url or None,
        "products_path": settings.wordpress_products_path or None,
        "categories_path": settings.wordpress_categories_path or None,
        "store_api_path": settings.wordpress_store_products_path or None,
        "message": "Ready to pull the WooCommerce catalogue" if configured and credentials_ready else "Set the WooCommerce REST routes and server-only consumer key/secret",
    }


@router.post("/sync")
def sync_woocommerce_catalogue(
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("content_editor", "admin", "super_admin")),
) -> dict[str, Any]:
    settings = get_settings()
    required = [settings.wordpress_products_path, settings.wordpress_categories_path, settings.wordpress_store_products_path]
    if not settings.wordpress_api_base_url or not all(required):
        raise HTTPException(status_code=503, detail="Configure the WordPress URL and WooCommerce product, category, and Store API routes")
    if not settings.wordpress_consumer_key or not settings.wordpress_consumer_secret:
        raise HTTPException(status_code=503, detail="Set WORDPRESS_CONSUMER_KEY and WORDPRESS_CONSUMER_SECRET in the API environment")

    # Pull-only sync: the WooCommerce API is the catalog source; app records are upserted here.
    source_products = _fetch_all(settings.wordpress_products_path, authenticated=True, extra_params={"status": "publish"})
    if not source_products:
        raise HTTPException(status_code=409, detail="WooCommerce returned no products; sync made no changes")
    source_categories = _fetch_all(settings.wordpress_categories_path, authenticated=True, extra_params={"hide_empty": "false"})
    store_products = _fetch_all(settings.wordpress_store_products_path, authenticated=False)
    store_by_id = {str(row.get("id")): row for row in store_products if row.get("id") is not None}
    source_media = _fetch_all(settings.wordpress_documents_path, authenticated=False, extra_params={"mime_type": "application/pdf"}) if settings.wordpress_documents_path else []

    categories_by_wp_id: dict[str, ProductCategory] = {}
    category_rows = 0
    for item in source_categories:
        wp_id = str(item.get("id", ""))
        name = _plain(item.get("name"), 180)
        if not wp_id or not name:
            continue
        slug = str(item.get("slug") or f"category-{wp_id}")[:120]
        category = session.scalar(select(ProductCategory).where(ProductCategory.wordpress_source_id == wp_id))
        if category is None:
            slug_match = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if slug_match is not None and slug_match.wordpress_source_id in (None, wp_id):
                category = slug_match
        image = _image_url(item.get("image"))
        description = _plain(item.get("description"), 3000) or None
        if category is None:
            collision = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if collision is not None:
                suffix = f"-wp-{wp_id}"
                slug = f"{slug[:120-len(suffix)]}{suffix}"
            category = ProductCategory(slug=slug, name=name, description=description, sort_order=int(item.get("menu_order") or 0), image_url=image, wordpress_source_id=wp_id, is_published=True)
            session.add(category)
        else:
            slug_conflict = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if slug_conflict is not None and slug_conflict.id != category.id:
                suffix = f"-wp-{wp_id}"
                slug = f"{slug[:120-len(suffix)]}{suffix}"
            category.slug = slug
            category.name = name
            category.description = description
            category.sort_order = int(item.get("menu_order") or 0)
            category.image_url = image
            category.wordpress_source_id = wp_id
            category.is_published = True
        categories_by_wp_id[wp_id] = category
        category_rows += 1
    session.flush()

    created = updated = skipped = 0
    source_wp_ids = {str(row.get("id")) for row in source_products if row.get("id") is not None}
    for source in source_products:
        wp_id = str(source.get("id", ""))
        wp_categories = source.get("categories") if isinstance(source.get("categories"), list) else []
        selected_category = next((categories_by_wp_id.get(str(row.get("id"))) for row in wp_categories if isinstance(row, dict) and categories_by_wp_id.get(str(row.get("id"))) is not None), None)
        if not wp_id or selected_category is None:
            skipped += 1
            continue

        store = store_by_id.get(wp_id, {})
        title = _plain(_field(source, settings.wordpress_source_title_field, source.get("name", "")), 220)
        slug = str(_field(source, settings.wordpress_source_slug_field, source.get("slug", "")))[:180]
        if len(title) < 2:
            skipped += 1
            continue
        permalink = _https_url(source.get("permalink"))
        if not slug:
            slug = f"wordpress-product-{wp_id}"
        product = session.scalar(select(Product).where(Product.wordpress_source_id == wp_id))
        slug = _slug_for_product(session, slug, wp_id, product)
        summary = _plain(_field(source, settings.wordpress_source_summary_field, source.get("short_description", "")), 500) or None
        description = _plain(_field(source, settings.wordpress_source_description_field, source.get("description", "")), 12000, preserve_blocks=True) or None
        sku = _plain(_field(source, settings.wordpress_source_model_field, source.get("sku", "")), 120) or None
        images = source.get("images") if isinstance(source.get("images"), list) else store.get("images", [])
        image_url = _image_url(_field(source, settings.wordpress_source_image_field)) or (_image_url(_field(store, "images.0")))
        gallery = [_image_url(image) for image in images if isinstance(images, list)] if isinstance(images, list) else []
        gallery_images = list(dict.fromkeys(url for url in gallery if url and url != image_url))[:16]

        attributes = _field(source, settings.wordpress_source_specifications_field, source.get("attributes", []))
        specifications = _specifications(attributes)
        applications = _string_list(_field(source, settings.wordpress_source_applications_field, []), 24)
        features = _string_list(_field(source, settings.wordpress_source_features_field, []), 32)
        store_prices = store.get("prices") if isinstance(store.get("prices"), dict) else {}
        currency = _safe_currency(store_prices.get("currency_code") or source.get("currency"))
        minor_digits = int(store_prices.get("currency_minor_unit", 2) or 0)
        price_minor = _minor_units(store_prices.get("price"), minor_digits, already_minor=True)
        if price_minor is None:
            price_minor = _minor_units(source.get("price"), minor_digits)
        stock_status = str(source.get("stock_status") or "unknown")
        if store.get("is_in_stock") is False:
            stock_status = "outofstock"
        elif store.get("is_in_stock") is True and stock_status == "unknown":
            stock_status = "instock"
        if stock_status not in {"instock", "outofstock", "onbackorder"}:
            stock_status = "unknown"
        quantity = source.get("stock_quantity")
        try:
            quantity = int(quantity) if quantity is not None and int(quantity) >= 0 else None
        except (TypeError, ValueError):
            quantity = None
        documents = _documents(source, source_media)
        values = {
            "category_id": str(selected_category.id), "slug": slug, "name": title,
            "model_code": sku, "summary": summary, "description": description,
            "applications": applications, "features": features, "specifications": specifications,
            "image_url": image_url, "gallery_images": gallery_images,
            "price_minor": price_minor, "currency_code": currency,
            "currency_minor_unit": minor_digits,
            "stock_status": stock_status, "stock_quantity": quantity,
            "documents": documents, "source_reference": permalink,
            "wordpress_source_id": wp_id, "wordpress_source_url": permalink,
        }
        if product is None:
            product = Product(category_id=selected_category.id, slug=slug, name=title, model_code=sku, is_published=True, wordpress_source_id=wp_id)
            session.add(product)
            created += 1
        else:
            updated += 1
        product.category_id = selected_category.id
        product.slug = slug
        product.name = title
        product.model_code = sku
        product.summary = summary
        product.description = description
        product.applications = applications
        product.features = features
        product.specifications = specifications
        product.image_url = image_url
        product.gallery_images = gallery_images
        product.price_minor = price_minor
        product.currency_code = currency
        product.currency_minor_unit = minor_digits
        product.stock_status = stock_status
        product.stock_quantity = quantity
        product.documents = documents
        product.source_reference = permalink
        product.wordpress_source_url = permalink
        product.content_verified_at = datetime.now(timezone.utc)
        product.published_at = product.published_at or datetime.now(timezone.utc)
        product.is_published = True
        product.draft_data = None

    # Products removed from WooCommerce are withdrawn only after every source page fetched successfully.
    withdrawn = 0
    for product in session.scalars(select(Product).where(Product.wordpress_source_id.is_not(None), Product.is_published.is_(True))):
        if product.wordpress_source_id not in source_wp_ids:
            product.is_published = False
            withdrawn += 1
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="wordpress.catalogue_synced",
        entity_type="catalogue_sync",
        entity_id="woocommerce",
        change_summary={"created": created, "updated": updated, "skipped": skipped, "withdrawn": withdrawn, "categories": category_rows, "source_products": len(source_products)},
    ))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        logger.exception("WooCommerce catalogue sync hit a database constraint")
        raise HTTPException(status_code=409, detail="WooCommerce sync could not be saved because of a catalogue conflict. Check for duplicate product or collection slugs.") from error
    except Exception as error:
        session.rollback()
        logger.exception("WooCommerce catalogue sync could not commit")
        raise HTTPException(status_code=500, detail="WooCommerce sync could not be saved. Check API runtime logs and try again.") from error
    return {
        "source": "woocommerce",
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "withdrawn": withdrawn,
        "categories": category_rows,
        "documents_linked": sum(len(_documents(row, source_media)) for row in source_products),
        "message": f"Synced {created + updated} WooCommerce products to the app catalogue.",
    }


@router.get("/products")
def wordpress_products(
    limit: int = Query(default=20, ge=1, le=50),
    admin: AdminIdentity = Depends(require_admin_roles(*ROLES)),
) -> dict[str, Any]:
    rows, settings = _fetch(limit)
    result = []
    for row in rows:
        source_id = _field(row, settings.wordpress_source_id_field, row.get("id"))
        result.append({
            "id": str(source_id),
            "title": _plain(_field(row, settings.wordpress_source_title_field, row.get("title", "")), 220),
            "slug": str(_field(row, settings.wordpress_source_slug_field, row.get("slug", "")))[:180],
            "summary": _plain(_field(row, settings.wordpress_source_summary_field, row.get("excerpt", ""))),
            "model_code": _plain(_field(row, settings.wordpress_source_model_field, ""), 120),
            "description": _plain(_field(row, settings.wordpress_source_description_field, ""), 500),
            "image_url": _image_url(_field(row, settings.wordpress_source_image_field)),
            "link": str(row.get("link", ""))[:1000],
        })
    return {"items": result, "message": f"Fetched {len(result)} WordPress records. These are previews; import creates drafts."}


@router.post("/import")
def import_wordpress_product(
    body: WordPressImport,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*ROLES)),
) -> dict[str, Any]:
    category = session.get(ProductCategory, body.category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Choose a valid catalogue category")
    rows, settings = _fetch(50)
    source = next((row for row in rows if str(_field(row, settings.wordpress_source_id_field, row.get("id"))) == body.source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="WordPress product was not found in the first 50 published records")
    wp_id = str(_field(source, settings.wordpress_source_id_field, source.get("id")))
    existing = session.query(Product).filter(Product.wordpress_source_id == wp_id).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This WordPress product has already been imported")
    title = _plain(_field(source, settings.wordpress_source_title_field, source.get("title", "")), 220)
    slug = str(_field(source, settings.wordpress_source_slug_field, source.get("slug", "")))[:180]
    if len(title) < 2 or not slug or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in slug):
        raise HTTPException(status_code=422, detail="WordPress title or slug is not valid for the catalogue")
    summary = _plain(_field(source, settings.wordpress_source_summary_field, source.get("excerpt", "")))
    model = _plain(_field(source, settings.wordpress_source_model_field, ""), 120)
    description = _plain(_field(source, settings.wordpress_source_description_field, ""), 12000, preserve_blocks=True)
    image_url = _image_url(_field(source, settings.wordpress_source_image_field))
    gallery = _field(source, settings.wordpress_source_gallery_field, [])
    gallery_images = list(dict.fromkeys(url for item in (gallery if isinstance(gallery, list) else []) if (url := _image_url(item)) and url != image_url))[:16]
    applications = _string_list(_field(source, settings.wordpress_source_applications_field, []), 24)
    features = _string_list(_field(source, settings.wordpress_source_features_field, []), 32)
    specifications = _specifications(_field(source, settings.wordpress_source_specifications_field, {}))
    link = str(source.get("link", ""))[:1000]
    values = {
        "category_id": str(category.id), "slug": slug, "name": title,
        "model_code": model or None, "summary": summary or None, "description": description or None,
        "applications": applications, "features": features, "specifications": specifications, "image_url": image_url,
        "gallery_images": gallery_images, "source_reference": link or None,
        "wordpress_source_id": wp_id, "wordpress_source_url": link or None,
    }
    product = Product(category_id=category.id, slug=slug, name=title, model_code=model or None, summary=summary or None, description=description or None, image_url=image_url, gallery_images=gallery_images, applications=applications, features=features, specifications=specifications, is_published=False, wordpress_source_id=wp_id, wordpress_source_url=link or None, draft_data=values)
    session.add(product)
    session.add(AuditEvent(actor_uid=admin.uid, action="product.imported_from_wordpress", entity_type="product", entity_id=str(product.id), change_summary={"source_id": wp_id, "source_url": link}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug or WordPress source ID already exists") from error
    return {"id": str(product.id), "name": title, "is_published": False, "message": "Imported as a draft. Verify technical facts and source before publishing."}
