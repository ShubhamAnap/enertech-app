from dataclasses import dataclass, field
from typing import Iterable, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductCategory, ProductCategoryCatalogue


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

    def match_category_ids(self, category_ids: Iterable[UUID]) -> tuple[ProductCategoryCatalogue | None, ProductCategory | None]:
        for cid in category_ids:
            if cid in self.by_category_id:
                return self.by_category_id[cid], self.categories_by_id.get(cid)
            category = self.categories_by_id.get(cid)
            matched = self.match_category(category)
            if matched is not None:
                return matched, category
        return None, None


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


def resolve_product_documents(
    *,
    raw_documents: object,
    category_ids: Iterable[UUID],
    categories: Iterable[ProductCategory] = (),
    lookup: CategoryCatalogueLookup | None = None,
) -> tuple[list[dict[str, str]], str | None, Literal["product", "category", "none"]]:
    """Resolve documents and effective catalog_pdf_url using product-first, category-inherited fallback."""
    own_docs = normalize_pdf_documents(raw_documents)
    own_pdf = next((doc["url"] for doc in own_docs if _is_pdf_document(doc)), None)
    if own_pdf is not None:
        return own_docs, own_pdf, "product"
    if own_docs:
        return own_docs, own_docs[0]["url"], "product"

    if lookup is not None:
        ordered_categories = list(categories)
        matched_mapping: ProductCategoryCatalogue | None = None
        matched_category: ProductCategory | None = None
        for cat in ordered_categories:
            matched_mapping = lookup.match_category(cat)
            if matched_mapping is not None:
                matched_category = cat
                break
        if matched_mapping is None:
            matched_mapping, matched_category = lookup.match_category_ids(category_ids)
        if matched_mapping is not None and matched_mapping.catalog_pdf_url.startswith("https://"):
            default_title = f"{matched_category.name} Catalogue PDF" if matched_category else "Category catalogue PDF"
            title = (matched_mapping.title or default_title).strip()[:180]
            inherited_doc = {"title": title, "url": matched_mapping.catalog_pdf_url[:1000]}
            return [inherited_doc], matched_mapping.catalog_pdf_url[:1000], "category"

    return [], None, "none"


def resolve_product_documents_for_model(
    product: Product,
    lookup: CategoryCatalogueLookup | None,
) -> tuple[list[dict[str, str]], str | None, Literal["product", "category", "none"]]:
    categories = list(product.categories)
    if product.category is not None and all(c.id != product.category.id for c in categories):
        categories.append(product.category)
    return resolve_product_documents(
        raw_documents=product.documents,
        category_ids=product.category_ids,
        categories=categories,
        lookup=lookup,
    )
