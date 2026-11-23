"""
Standalone CLI script to migrate Supabase database and sync all WooCommerce products.
Run with:
    .venv/Scripts/python backend/sync_wordpress.py
"""

import os
import sys
from pathlib import Path

# Set up paths
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv(".env")

from app.core.config import get_settings
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.models import ProductCategory, Product, AuditEvent
from app.api.wordpress import (
    _fetch_all,
    _plain,
    _field,
    _image_url,
    _specifications,
    _string_list,
    _minor_units,
    _safe_currency,
    _https_url,
    _documents,
    _slug_for_product,
)
from datetime import datetime, timezone


def run_migration_and_sync():
    settings = get_settings()
    db_url = settings.active_database_url
    if not db_url or "127.0.0.1:55432" in db_url:
        print("\n[ERROR] Database is not configured!")
        print("Please set SUPABASE_DATABASE_URL in backend/.env with your Supabase connection string:")
        print("  SUPABASE_DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require\n")
        return False

    print(f"\n[1/3] Connecting to database: {db_url.split('@')[-1] if '@' in db_url else db_url}...")
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            print("  -> Database connection SUCCESSFUL!")
    except Exception as e:
        print(f"  -> [ERROR] Failed to connect to database: {e}")
        return False

    print("\n[2/3] Applying Alembic database migrations...")
    try:
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")
        print("  -> Database tables verified/migrated successfully!")
    except Exception as e:
        print(f"  -> Migration error (or tables already exist): {e}")

    print("\n[3/3] Syncing WooCommerce catalogue from enertechups.com...")
    if not settings.wordpress_consumer_key or not settings.wordpress_consumer_secret:
        print("  -> [ERROR] WORDPRESS_CONSUMER_KEY and WORDPRESS_CONSUMER_SECRET must be set in backend/.env")
        return False

    SessionMaker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionMaker() as session:
        print("  -> Fetching published products from WordPress REST API...")
        source_products = _fetch_all(settings.wordpress_products_path, authenticated=True, extra_params={"status": "publish"})
        print(f"  -> Fetched {len(source_products)} published products.")

        print("  -> Fetching product categories...")
        source_categories = _fetch_all(settings.wordpress_categories_path, authenticated=True, extra_params={"hide_empty": "false"})
        print(f"  -> Fetched {len(source_categories)} categories.")

        print("  -> Fetching Store API products & media...")
        store_products = _fetch_all(settings.wordpress_store_products_path, authenticated=False)
        store_by_id = {str(row.get("id")): row for row in store_products if row.get("id") is not None}
        source_media = _fetch_all(settings.wordpress_documents_path, authenticated=False, extra_params={"mime_type": "application/pdf"}) if settings.wordpress_documents_path else []

        categories_by_wp_id = {}
        cat_count = 0
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
            cat_count += 1
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
            description = _plain(_field(source, settings.wordpress_source_description_field, source.get("description", "")), 12000) or None
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

            if product is None:
                product = Product(
                    category_id=selected_category.id,
                    slug=slug,
                    name=title,
                    model_code=sku,
                    is_published=True,
                    wordpress_source_id=wp_id,
                )
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

        session.commit()
        print(f"\n[DONE] Successfully synced!")
        print(f"  Categories: {cat_count}")
        print(f"  Products Created: {created}")
        print(f"  Products Updated: {updated}")
        print(f"  Skipped (e.g. no category): {skipped}")
        return True


if __name__ == "__main__":
    run_migration_and_sync()
