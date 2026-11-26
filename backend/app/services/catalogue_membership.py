from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProductCategory


def staging_tag(session: Session) -> ProductCategory:
    slug = "uncategorized"
    suffix = 0
    while (category := session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))) is not None:
        if not category.is_app_collection and category.wordpress_source_id is None:
            return category
        suffix += 1
        slug = f"wp-staging-{suffix}"
    category = ProductCategory(slug=slug, name="Unassigned", is_app_collection=False, is_published=False)
    session.add(category)
    session.flush()
    return category
