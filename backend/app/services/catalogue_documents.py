from dataclasses import dataclass, field
from typing import Iterable, Literal
from uuid import UUID

from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from app.models import Product, ProductCategory, ProductCategoryCatalogue
from app.models.catalogue import product_category_links


def normalize_pdf_documents(raw_documents: object) -> list[dict[str, str]]:
    """Return deduplicated HTTPS document entries with normalized title and url."""
    if not isinstance(raw_documents, list):
        return []
    seen_urls: set[str] = set()
    normalized: list[dict[str, str]] = []
    for item in raw_documents:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith("https://") or url in seen_urls:
            continue
        title = str(item.get("title") or "Product catalogue PDF").strip() or "Product catalogue PDF"
        seen_urls.add(url)
        normalized.append({"title": title[:180], "url": url[:1000]})
    return normalized


def _is_pdf_document(doc: dict[str, str]) -> bool:
    url_path = doc["url"].lower().split("?", 1)[0].split("#", 1)[0]
    title = doc["title"].lower()
    return url_path.endswith(".pdf") or any(word in title for word in ("pdf", "catalogue", "catalog", "brochure", "datasheet"))


@dataclass
class CategoryCatalogueLookup:
    by_category_id: dict[UUID, ProductCategoryCatalogue] = field(default_factory=dict)
    by_wp_category_id: dict[str, ProductCategoryCatalogue] = field(default_factory=dict)
    by_key: dict[str, ProductCategoryCatalogue] = field(default_factory=dict)
    categories_by_id: dict[UUID, ProductCategory] = field(default_factory=dict)

    def match_category(self, category: ProductCategory | None) -> ProductCategoryCatalogue | None:
        if category is None:
            return None
        if category.id in self.by_category_id:
            return self.by_category_id[category.id]
        if category.wordpress_source_id and category.wordpress_source_id in self.by_wp_category_id:
            return self.by_wp_category_id[category.wordpress_source_id]
        slug_key = category.slug.strip().lower()
        if slug_key in self.by_key:
            return self.by_key[slug_key]
        if category.wordpress_source_id:
            wp_key = f"wp:{category.wordpress_source_id}"
            if wp_key in self.by_key:
                return self.by_key[wp_key]
        return None



def load_category_catalogue_lookup(session: Session) -> CategoryCatalogueLookup:
    """Load category catalogue mappings and categories in two flat queries."""
    mappings = list(session.scalars(select(ProductCategoryCatalogue)))
    categories = list(session.scalars(select(ProductCategory)))
    lookup = CategoryCatalogueLookup(
        categories_by_id={cat.id: cat for cat in categories},
    )
    for mapping in mappings:
        if not mapping.catalog_pdf_url or not mapping.catalog_pdf_url.startswith("https://"):
            continue
        if mapping.category_id is not None:
            lookup.by_category_id[mapping.category_id] = mapping
        if mapping.wordpress_category_id:
            lookup.by_wp_category_id[mapping.wordpress_category_id] = mapping
        if mapping.category_key:
            lookup.by_key[mapping.category_key.strip().lower()] = mapping
    return lookup


def _order_collection_categories(
    categories: Iterable[ProductCategory],
    *,
    preferred_category_slug: str | None = None,
    require_published: bool = False,
    app_collections_only: bool = True,
) -> list[ProductCategory]:
    eligible: list[ProductCategory] = []
    seen_ids: set[UUID] = set()
    for cat in categories:
        if cat is None or cat.id in seen_ids:
            continue
        if app_collections_only and cat.is_app_collection is False:
            continue
        if require_published and not cat.is_published:
            continue
        seen_ids.add(cat.id)
        eligible.append(cat)

    if preferred_category_slug:
        slug_lower = preferred_category_slug.strip().lower()
        preferred = [cat for cat in eligible if cat.slug.strip().lower() == slug_lower]
        others = [cat for cat in eligible if cat.slug.strip().lower() != slug_lower]
        return [*preferred, *others]
    return eligible


def resolve_product_documents(
    *,
    raw_documents: object,
    category_ids: Iterable[UUID],
    categories: Iterable[ProductCategory] = (),
    lookup: CategoryCatalogueLookup | None = None,
    preferred_category_slug: str | None = None,
    require_published_collections: bool = False,
    app_collections_only: bool = True,
) -> tuple[list[dict[str, str]], str | None, Literal["product", "category", "none"]]:
    """Resolve documents using product-first, multi-collection brochure inheritance."""
    own_docs = normalize_pdf_documents(raw_documents)
    own_pdf = next((doc["url"] for doc in own_docs if _is_pdf_document(doc)), None)
    documents = list(own_docs)
    seen_urls = {doc["url"] for doc in documents}
    if lookup:
        collection_rows = [*categories, *(lookup.categories_by_id[cid] for cid in category_ids if cid in lookup.categories_by_id)]
        for category in _order_collection_categories(
            collection_rows, preferred_category_slug=preferred_category_slug,
            require_published=require_published_collections, app_collections_only=app_collections_only,
        ):
            mapping = lookup.match_category(category)
            if mapping and mapping.catalog_pdf_url not in seen_urls:
                documents.append({"title": mapping.title or f"{category.name} Catalogue PDF", "url": mapping.catalog_pdf_url})
                seen_urls.add(mapping.catalog_pdf_url)
    if own_docs:
        return documents, own_pdf or own_docs[0]["url"], "product"
    if documents:
        return documents, documents[0]["url"], "category"
    return [], None, "none"


def load_category_product_counts(
    session: Session,
    *,
    published_only: bool = False,
) -> dict[UUID, int]:
    """Return distinct product counts per category across primary and link memberships."""
    primary_query = select(
        Product.category_id.label("category_id"),
        Product.id.label("product_id"),
    )
    linked_query = select(
        product_category_links.c.category_id.label("category_id"),
        product_category_links.c.product_id.label("product_id"),
    ).join(Product, Product.id == product_category_links.c.product_id)
    if published_only:
        primary_query = primary_query.where(Product.is_published.is_(True))
        linked_query = linked_query.where(Product.is_published.is_(True))
    memberships = union(primary_query, linked_query).subquery()
    rows = session.execute(
        select(memberships.c.category_id, func.count(memberships.c.product_id))
        .group_by(memberships.c.category_id)
    )
    return {cat_id: int(count) for cat_id, count in rows if cat_id is not None}


def resolve_product_documents_for_model(
    product: Product,
    lookup: CategoryCatalogueLookup | None,
    *,
    preferred_category_slug: str | None = None,
    require_published_collections: bool = False,
    app_collections_only: bool = True,
) -> tuple[list[dict[str, str]], str | None, Literal["product", "category", "none"]]:
    # Prefer the browsed or primary collection brochure first, while including secondary collection PDFs.
    categories: list[ProductCategory] = []
    if product.category is not None:
        categories.append(product.category)
    for category in product.categories:
        if product.category is None or category.id != product.category.id:
            categories.append(category)
    ordered_ids = list(dict.fromkeys([product.category_id, *product.category_ids]))
    return resolve_product_documents(
        raw_documents=product.documents,
        category_ids=ordered_ids,
        categories=categories,
        lookup=lookup,
        preferred_category_slug=preferred_category_slug,
        require_published_collections=require_published_collections,
        app_collections_only=app_collections_only,
    )
