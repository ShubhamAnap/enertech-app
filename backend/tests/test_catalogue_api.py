from collections.abc import Iterator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.router as api_router
import app.core.auth as auth
import app.api.wordpress as wordpress_api
from app.core.auth import Identity, get_current_identity
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import AdminAccount, AppConfig, ContactInquiry, CustomerProfile, CustomerRequest, Product, ProductCategory
from app.core.auth import AdminIdentity


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        with TestSession() as session:
            yield session

    monkeypatch.setattr(api_router, "engine", test_engine)
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").json() == {"status": "ready"}


def test_production_readiness_requires_firebase_server_credentials(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_router, "get_settings", lambda: SimpleNamespace(
        app_env="production", firebase_project_id="enertech-ups", firebase_service_account_json="",
    ))
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Firebase Authentication is not configured"}


def test_database_outage_does_not_expose_connection_details(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db.session as database_session

    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, Exception("secret-host.internal password rejected"))

    monkeypatch.setattr(database_session, "SessionLocal", lambda: BrokenSession())
    app.dependency_overrides.pop(get_session, None)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "The database is temporarily unavailable. Please try again."}
    assert "secret-host.internal" not in response.text


def test_customer_requests_are_scoped_to_the_verified_identity(client: TestClient) -> None:
    identity = Identity("customer-a", "a@example.test", "Customer A", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    first = client.post("/api/v1/requests/quote", json={"application": "Factory", "equipment_or_load": "Production line"})
    assert first.status_code == 201

    identity = Identity("customer-b", "b@example.test", "Customer B", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    second = client.post("/api/v1/requests/quote", json={"application": "Office", "equipment_or_load": "Server rack"})
    assert second.status_code == 201
    rows = client.get("/api/v1/requests").json()
    assert len(rows) == 1
    assert rows[0]["id"] == second.json()["id"]


def test_admin_request_includes_profile_matched_by_firebase_uid(client: TestClient) -> None:
    admin = Identity("request-admin", "admin@example.test", "Admin", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: admin
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="request-admin", role="super_admin", is_active=True))
        session.add(CustomerProfile(
            firebase_uid="profile-customer", customer_type="end_user", name="Profile Customer",
            mobile_number="+919876543210", email="profile@example.test", location="Pune",
        ))
        session.add_all([
            CustomerRequest(customer_uid="profile-customer", customer_email="stale@example.test", kind="service", status="submitted", payload={"description": "Repair"}),
            CustomerRequest(customer_uid="no-profile", customer_email="no-profile@example.test", kind="service", status="submitted", payload={"description": "Inspect"}),
        ])
        session.commit()

    response = client.get("/api/v1/admin/requests?kind=service")
    assert response.status_code == 200
    by_email = {row["customer_email"]: row for row in response.json()}
    assert by_email["stale@example.test"]["customer_name"] == "Profile Customer"
    assert by_email["stale@example.test"]["customer_phone"] == "+919876543210"
    assert by_email["stale@example.test"]["customer_location"] == "Pune"
    assert by_email["no-profile@example.test"]["customer_name"] is None


def test_quote_and_service_requests_share_per_account_rate_limit(client: TestClient) -> None:
    identity = Identity("customer-a", "a@example.test", "Customer A", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    quote_body = {"application": "Factory", "equipment_or_load": "Production line"}
    service_body = {
        "product_model": "UPS-100", "problem_category": "other",
        "description": "The unit needs a technical inspection.", "service_location": "Pune",
    }

    for _ in range(5):
        assert client.post("/api/v1/requests/quote", json=quote_body).status_code == 201
        assert client.post("/api/v1/requests/service", json=service_body).status_code == 201
    assert client.post("/api/v1/requests/quote", json=quote_body).status_code == 429

    identity = Identity("customer-b", "b@example.test", "Customer B", {"email_verified": True})
    assert client.post("/api/v1/requests/service", json=service_body).status_code == 201


def test_contact_inquiry_rate_limit_uses_customer_uid_not_mutable_email(client: TestClient) -> None:
    identity = Identity("customer-a", "a@example.test", "Customer A", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    body = {"name": "Customer A", "phone": "+1 555 555 5555", "message": "Please contact me"}

    for _ in range(5):
        response = client.post("/api/v1/requests/contact-inquiry", json=body)
        assert response.status_code == 201

    identity = Identity("customer-a", "new-address@example.test", "Customer A", {"email_verified": True})
    assert client.post("/api/v1/requests/contact-inquiry", json=body).status_code == 429

    identity = Identity("customer-b", "b@example.test", "Customer B", {"email_verified": True})
    assert client.post("/api/v1/requests/contact-inquiry", json=body).status_code == 201
    with Session(api_router.engine) as session:
        rows = session.query(ContactInquiry).all()
        assert len(rows) == 6
        assert {row.customer_uid for row in rows} == {"customer-a", "customer-b"}


def test_content_editor_cannot_read_customer_directory(client: TestClient) -> None:
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="editor-uid", role="content_editor", is_active=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "editor-uid", "editor@example.test", "Editor", {"email_verified": True}
    )

    assert client.get("/api/v1/admin/catalogue/categories").status_code == 200
    assert client.get("/api/v1/admin/customers").status_code == 403


def test_closed_request_cannot_be_reopened_by_admin(client: TestClient) -> None:
    request_id = uuid4()
    now = datetime.now(timezone.utc)
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="admin-uid", role="admin", is_active=True))
        session.add(CustomerRequest(
            id=request_id, customer_uid="customer-uid", customer_email="customer@example.test",
            kind="service", status="closed", payload={}, created_at=now, updated_at=now,
        ))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "admin-uid", "admin@example.test", "Admin", {"email_verified": True}
    )

    response = client.patch(f"/api/v1/admin/requests/{request_id}", json={"status": "in_review"})
    assert response.status_code == 409
    with Session(api_router.engine) as session:
        assert session.get(CustomerRequest, request_id).status == "closed"


def test_bootstrap_admin_role_and_deactivation_follow_managed_account(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(bootstrap_admin_uids={"bootstrap-uid"}))
    identity = Identity("bootstrap-uid", "bootstrap@example.test", "Bootstrap", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    assert client.get("/api/v1/admin/session").json()["role"] == "super_admin"

    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="bootstrap-uid", role="admin", is_active=True))
        session.add(AdminAccount(firebase_uid="other-super", role="super_admin", is_active=True))
        session.commit()

    assert client.get("/api/v1/admin/session").json()["role"] == "admin"
    assert client.get("/api/v1/admin/accounts").status_code == 403

    identity = Identity("other-super", "other@example.test", "Other Super", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    updated = client.put("/api/v1/admin/accounts/bootstrap-uid", json={
        "firebase_uid": "bootstrap-uid", "email": "bootstrap@example.test",
        "display_name": "Bootstrap", "role": "admin", "is_active": False,
    })
    assert updated.status_code == 200

    identity = Identity("bootstrap-uid", "bootstrap@example.test", "Bootstrap", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    assert client.get("/api/v1/admin/session").status_code == 403


def test_empty_catalogue_is_a_real_empty_result(client: TestClient) -> None:
    assert client.get("/api/v1/catalogue/categories").json() == []
    response = client.get("/api/v1/catalogue/products")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}


def test_catalogue_hides_unpublished_rows_and_paginates(client: TestClient) -> None:
    test_engine = api_router.engine
    with Session(test_engine) as session:
        category = ProductCategory(slug="verified-test-category", name="Test category", is_published=True)
        hidden_category = ProductCategory(slug="hidden-test-category", name="Hidden category", is_published=False)
        session.add_all([category, hidden_category])
        session.flush()
        session.add_all([
            Product(slug="test-visible-a", name="Test visible A", category_id=category.id, is_published=True),
            Product(slug="test-visible-b", name="Test visible B", category_id=category.id, is_published=True),
            Product(slug="test-draft", name="Test draft", category_id=category.id, is_published=False),
            Product(slug="test-hidden-category", name="Test hidden category", category_id=hidden_category.id, is_published=True),
        ])
        session.commit()

    response = client.get("/api/v1/catalogue/products?limit=1&offset=0")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1
    assert client.get("/api/v1/catalogue/products?q=visible").json()["total"] == 2
    assert client.get("/api/v1/catalogue/products?category=hidden-test-category").json()["total"] == 0
    assert client.get("/api/v1/catalogue/categories").json()[0]["slug"] == "verified-test-category"


def test_catalogue_accepts_cms_max_page_size(client: TestClient) -> None:
    response = client.get("/api/v1/catalogue/products?limit=500")
    assert response.status_code == 200
    assert response.json()["limit"] == 500


def test_catalogue_can_fetch_published_featured_products_by_id(client: TestClient) -> None:
    with Session(api_router.engine) as session:
        category = ProductCategory(slug="featured-id-category", name="Featured ID", is_published=True)
        session.add(category)
        session.flush()
        hidden_category = ProductCategory(slug="featured-hidden-category", name="Hidden", is_published=False)
        session.add(hidden_category)
        session.flush()
        target = Product(slug="featured-after-first-page", name="ZZZ Featured", category_id=category.id, is_published=True)
        hidden = Product(slug="featured-unpublished", name="Unpublished", category_id=category.id, is_published=False)
        hidden_parent = Product(slug="featured-hidden-parent", name="Hidden parent", category_id=hidden_category.id, is_published=True)
        session.add_all([target, hidden, hidden_parent])
        session.flush()
        for index in range(300):
            session.add(Product(slug=f"feature-page-{index:03}", name=f"Product {index:03}", category_id=category.id, is_published=True))
        session.commit()
        target_id, hidden_id, hidden_parent_id = target.id, hidden.id, hidden_parent.id

    response = client.get(f"/api/v1/catalogue/products?ids={target_id},{hidden_id},{hidden_parent_id}&limit=12")
    assert response.status_code == 200
    assert [product["id"] for product in response.json()["items"]] == [str(target_id)]
    assert response.json()["total"] == 1


def test_catalogue_keeps_all_product_category_memberships(client: TestClient) -> None:
    with Session(api_router.engine) as session:
        primary = ProductCategory(slug="multi-primary", name="Primary", is_published=True)
        secondary = ProductCategory(slug="multi-secondary", name="Secondary", is_published=True)
        hidden = ProductCategory(slug="multi-hidden", name="Hidden", is_published=False)
        session.add_all([primary, secondary, hidden])
        session.flush()
        product = Product(slug="multi-category-product", name="Multi category", category_id=primary.id, categories=[primary, secondary, hidden], is_published=True)
        session.add(product)
        session.commit()
        product_id = product.id
        expected_category_ids = {str(primary.id), str(secondary.id)}

    primary_result = client.get("/api/v1/catalogue/products?category=multi-primary").json()
    secondary_result = client.get("/api/v1/catalogue/products?category=multi-secondary").json()
    hidden_result = client.get("/api/v1/catalogue/products?category=multi-hidden").json()
    assert [row["id"] for row in primary_result["items"]] == [str(product_id)]
    assert [row["id"] for row in secondary_result["items"]] == [str(product_id)]
    assert hidden_result["items"] == []
    assert set(primary_result["items"][0]["category_ids"]) == expected_category_ids


def test_cms_product_create_edit_publish_keeps_multiple_collections(client: TestClient) -> None:
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="catalogue-admin", role="admin", is_active=True))
        categories = [
            ProductCategory(slug=f"cms-multi-{index}", name=f"CMS collection {index}", is_published=True)
            for index in range(3)
        ]
        session.add_all(categories)
        session.commit()
        category_ids = [str(category.id) for category in categories]
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "catalogue-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    response = client.post("/api/v1/admin/catalogue/products", json={
        "category_id": category_ids[0], "category_ids": category_ids[:2],
        "slug": "cms-multi-collection", "name": "CMS multi collection product",
        "source_reference": "verified test source",
    })
    assert response.status_code == 201, response.text
    product = response.json()
    assert set(product["category_ids"]) == set(category_ids[:2])

    updated = client.patch(f"/api/v1/admin/catalogue/products/{product['id']}", json={
        "category_ids": category_ids,
    })
    assert updated.status_code == 200, updated.text
    assert set(updated.json()["category_ids"]) == set(category_ids)

    published = client.post(f"/api/v1/admin/catalogue/products/{product['id']}/publish")
    assert published.status_code == 200, published.text
    assert set(published.json()["category_ids"]) == set(category_ids)
    public_catalogue = client.get("/api/v1/catalogue/products?category=cms-multi-2")
    assert public_catalogue.status_code == 200
    assert [item["id"] for item in public_catalogue.json()["items"]] == [product["id"]]


def test_create_collection_with_pdf_and_full_product_checklist(client: TestClient) -> None:
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="curator", role="admin", is_active=True))
        source = ProductCategory(slug="wp-source", name="Source", is_app_collection=False)
        session.add(source)
        session.flush()
        products = [
            Product(slug=f"curated-product-{index}", name=f"Product {index}", category_id=source.id,
                    wordpress_source_id=str(index), is_published=True)
            for index in range(2)
        ]
        session.add_all(products)
        session.commit()
        ids = [str(product.id) for product in products]
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "curator", "curator@example.test", "Curator", {"email_verified": True}
    )
    base = "/api/v1/admin/catalogue/categories"
    options = client.get(f"{base}/product-options")
    assert options.status_code == 200
    assert {row["id"] for row in options.json()["products"]} == set(ids)
    created = client.post(f"{base}/curate", json={
        "name": "Solar Hybrid UPS", "catalog_pdf_url": "https://example.test/solar.pdf", "product_ids": ids,
    })
    assert created.status_code == 201, created.text
    assert created.json()["slug"] == "solar-hybrid-ups"
    assert created.json()["is_published"] is True
    assert created.json()["product_count"] == 2
    assert {row["slug"] for row in client.get("/api/v1/catalogue/categories").json()} == {"solar-hybrid-ups"}
    rows = client.get("/api/v1/catalogue/products").json()["items"]
    assert len(rows) == 2
    assert all(row["catalog_pdf_url"] == "https://example.test/solar.pdf" for row in rows)
    duplicate = client.post(f"{base}/curate", json={
        "name": "Solar Hybrid UPS", "catalog_pdf_url": "https://example.test/second.pdf", "product_ids": ids[:1],
    })
    assert duplicate.status_code == 201
    assert duplicate.json()["slug"] == "solar-hybrid-ups-2"
    updated = client.put(f"{base}/{created.json()['id']}/curate", json={
        "name": "Solar UPS", "catalog_pdf_url": "https://example.test/updated.pdf", "product_ids": ids[:1],
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["product_count"] == 1
    assert updated.json()["name"] == "Solar UPS"
    page = client.get("/api/v1/catalogue/products?category=solar-hybrid-ups").json()
    assert page["total"] == 1
    assert page["items"][0]["catalog_pdf_url"] == "https://example.test/updated.pdf"


def test_woocommerce_sync_imports_all_product_categories(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        wordpress_api_base_url="https://store.example.test/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="wc/store/v1/products",
        wordpress_documents_path="",
        wordpress_consumer_key="consumer-key",
        wordpress_consumer_secret="consumer-secret",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
    )
    rows = {
        "wc/v3/products": [
            {
                "id": 913, "name": "Woo multi-category product", "slug": "woo-multi-category-product",
                "sku": "WMC-913", "description": "<p>Product copy</p>", "short_description": "",
                "permalink": "https://store.example.test/product/woo-multi-category-product/",
                "images": [{"src": "https://store.example.test/product.png"}],
                "categories": [{"id": 41}, {"id": 42}], "attributes": [], "price": "125.00",
                "stock_status": "instock",
            },
            {
                "id": 914, "name": "Woo uncategorized product", "slug": "woo-uncategorized-product",
                "sku": "WUC-914", "description": "", "short_description": "",
                "permalink": "https://store.example.test/product/woo-uncategorized-product/",
                "images": [], "categories": [], "attributes": [], "price": "0", "stock_status": "unknown",
            },
        ],
        "wc/v3/products/categories": [
            {"id": 41, "name": "Solar", "slug": "solar"},
            {"id": 42, "name": "Hybrid", "slug": "hybrid"},
        ],
        "wc/store/v1/products": [],
    }
    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    monkeypatch.setattr(wordpress_api, "_fetch_all", lambda path, **_kwargs: rows.get(path, []))
    with Session(api_router.engine) as session:
        result = wordpress_api.sync_woocommerce_catalogue(session, AdminIdentity("admin-uid", None, "Admin", "super_admin"))
        product = session.query(Product).filter_by(wordpress_source_id="913").one()
        expected_slugs = {"solar", "hybrid"}
        assert {category.slug for category in product.categories} == expected_slugs
        uncategorized = session.query(Product).filter_by(wordpress_source_id="914").one()
        assert [category.slug for category in uncategorized.categories] == ["uncategorized"]
        assert result["created"] == 2


def test_woocommerce_sync_falls_back_to_public_store_api_without_rest_keys(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        wordpress_api_base_url="https://store.example.test/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="wc/store/v1/products",
        wordpress_documents_path="",
        wordpress_consumer_key="",
        wordpress_consumer_secret="",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
    )
    public_product = {
        "id": 991, "name": "Public API Solar Product", "slug": "public-api-solar-product",
        "sku": "PUBLIC-991", "description": "A public Store API product", "short_description": "Solar",
        "permalink": "https://store.example.test/product/public-api-solar-product/",
        "images": [{"src": "https://store.example.test/uploads/public-product.png"}],
        "categories": [{"id": 71, "name": "Public Solar", "slug": "public-solar"}],
        "prices": {"price": "129900", "regular_price": "149900", "sale_price": "129900", "currency_code": "INR", "currency_minor_unit": 2},
        "is_in_stock": True,
    }
    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)

    def fetch(path: str, *, authenticated: bool, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        assert authenticated is False
        assert path == "wc/store/v1/products"
        return [public_product]

    monkeypatch.setattr(wordpress_api, "_fetch_all", fetch)
    with Session(api_router.engine) as session:
        result = wordpress_api.sync_woocommerce_catalogue(session, AdminIdentity("admin-uid", None, "Admin", "super_admin"))
        product = session.query(Product).filter_by(wordpress_source_id="991").one()
        assert product.name == "Public API Solar Product"
        assert product.price_minor == 129900
        assert product.currency_code == "INR"
        assert product.image_url == "https://store.example.test/uploads/public-product.png"
        assert [category.slug for category in product.categories] == ["public-solar"]
        assert result["created"] == 1


def test_catalogue_rejects_invalid_featured_product_ids(client: TestClient) -> None:
    assert client.get("/api/v1/catalogue/products?ids=not-a-uuid").status_code == 422
    assert client.get("/api/v1/catalogue/products?ids=" + ",".join(str(uuid4()) for _ in range(13))).status_code == 422


def test_woocommerce_products_keep_content_locked_while_allowing_category_and_pdf_overrides(client: TestClient) -> None:
    category_id, alt_category_id, product_id = uuid4(), uuid4(), uuid4()
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="catalogue-admin", role="admin", is_active=True))
        session.add_all([
            ProductCategory(id=category_id, slug="wp-read-only", name="WooCommerce collection", wordpress_source_id="wp-category-90", is_app_collection=False, is_published=False),
            ProductCategory(id=alt_category_id, slug="cms-curated-cat", name="Curated UPS", is_published=True),
        ])
        session.add(Product(id=product_id, category_id=category_id, slug="wp-read-only-product", name="WooCommerce product", wordpress_source_id="wp-product-90", is_published=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "catalogue-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    # Full content edits and destructive deletes remain protected for WooCommerce-sourced records.
    assert client.patch(f"/api/v1/admin/catalogue/products/{product_id}", json={"name": "Local override"}).status_code == 409
    assert client.post(f"/api/v1/admin/catalogue/products/{product_id}/publish").status_code == 409
    assert client.delete(f"/api/v1/admin/catalogue/products/{product_id}").status_code == 409
    assert client.delete(f"/api/v1/admin/catalogue/categories/{category_id}").status_code == 409
    assert client.patch(f"/api/v1/admin/catalogue/categories/{category_id}", json={"slug": "changed-slug"}).status_code == 409

    assert client.post(f"/api/v1/admin/catalogue/categories/{category_id}/publish").status_code == 409
    assert client.patch(f"/api/v1/admin/catalogue/categories/{category_id}", json={"name": "Online UPS"}).status_code == 409

    # CMS can reassign a WooCommerce product's collection & PDF independently.
    cat_override = client.put(
        f"/api/v1/admin/catalogue/products/{product_id}/categories",
        json={"category_id": str(alt_category_id), "category_ids": [str(alt_category_id)]},
    )
    assert cat_override.status_code == 200
    assert cat_override.json()["category_id"] == str(alt_category_id)
    assert cat_override.json()["category_override"] is True

    pdf_override = client.put(
        f"/api/v1/admin/catalogue/products/{product_id}/pdf",
        json={"title": "Verified Datasheet", "url": "https://cdn.example.test/enertech-public/cms/verified.pdf"},
    )
    assert pdf_override.status_code == 200
    assert pdf_override.json()["catalog_pdf_url"] == "https://cdn.example.test/enertech-public/cms/verified.pdf"
    assert pdf_override.json()["documents_override"] is True

    pdf_cleared = client.delete(f"/api/v1/admin/catalogue/products/{product_id}/pdf")
    assert pdf_cleared.status_code == 200
    assert pdf_cleared.json()["documents_override"] is True
    assert pdf_cleared.json()["catalog_pdf_url"] is None


def test_admin_product_page_accepts_product_admin_items(client: TestClient) -> None:
    category_id, product_id = uuid4(), uuid4()
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="catalogue-admin", role="admin", is_active=True))
        session.add(ProductCategory(id=category_id, slug="admin-list-category", name="Admin list", is_published=True))
        session.add(Product(
            id=product_id,
            category_id=category_id,
            slug="admin-list-product",
            name="Admin list product",
            wordpress_source_id="wp-product-91",
            is_published=True,
        ))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "catalogue-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    response = client.get("/api/v1/admin/catalogue/products")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == str(product_id)


def test_catalogue_deletes_reject_product_and_home_references(client: TestClient) -> None:
    category_id, featured_category_id = uuid4(), uuid4()
    product_id, featured_product_id = uuid4(), uuid4()
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="catalogue-admin", role="admin", is_active=True))
        session.add_all([
            ProductCategory(id=category_id, slug="has-products", name="Has products"),
            ProductCategory(id=featured_category_id, slug="home-category", name="Home category"),
        ])
        session.add_all([
            Product(id=product_id, category_id=category_id, slug="category-product", name="Category product"),
            Product(id=featured_product_id, category_id=category_id, slug="home-product", name="Home product"),
        ])
        session.add(AppConfig(
            key="home",
            draft_payload={"featured_product_ids": [str(featured_product_id)], "featured_category_ids": [str(featured_category_id)]},
            published_payload={"featured_product_ids": [], "featured_category_ids": []},
        ))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "catalogue-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    product_response = client.delete(f"/api/v1/admin/catalogue/products/{featured_product_id}")
    category_response = client.delete(f"/api/v1/admin/catalogue/categories/{featured_category_id}")
    dependent_category_response = client.delete(f"/api/v1/admin/catalogue/categories/{category_id}")
    assert product_response.status_code == 409
    assert "Home featured products" in product_response.json()["detail"]
    assert category_response.status_code == 409
    assert "Home featured collections" in category_response.json()["detail"]
    assert dependent_category_response.status_code == 409
    assert "products in this collection" in dependent_category_response.json()["detail"]


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "q=" + ("x" * 121)])
def test_invalid_catalogue_parameters_are_rejected(client: TestClient, query: str) -> None:
    assert client.get(f"/api/v1/catalogue/products?{query}").status_code == 422


def publish_collection(client, slug, product_ids, pdf_url=None):
    base = "/api/v1/admin/catalogue/categories"
    result = client.post(base, json={"slug": slug, "name": slug.title(), "catalog_pdf_url": pdf_url})
    assert result.status_code == 201, result.text
    cid = result.json()["id"]
    assert client.put(f"{base}/{cid}/products", json={"product_ids": product_ids}).status_code == 200
    assert client.post(f"{base}/{cid}/publish").status_code == 200
    return cid


def test_end_to_end_wordpress_sync_category_pdf_inheritance_and_preservation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://enertechups.com/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="wc/store/v1/products",
        wordpress_documents_path="wp/v2/media",
        wordpress_wp_products_path="wp/v2/product",
        wordpress_consumer_key="ck_test",
        wordpress_consumer_secret="cs_test",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
        wordpress_source_documents_field="",
    )
    sync_datasets = [
        {
            "wc/v3/products/categories": [
                {
                    "id": 123,
                    "name": "Batteryless Solar Hybrid Inverter",
                    "slug": "batteryless-solar-hybrid-inverter",
                    "description": '<p><a href="https://enertechups.com/wp-content/uploads/batteryless-family.pdf">Download Brochure</a></p>',
                },
            ],
            "wc/v3/products": [
                {
                    "id": 3919,
                    "name": "Batteryless Gridless Solar Hybrid Inverter",
                    "slug": "batteryless-gridless-solar-hybrid-inverter",
                    "sku": "ET-BL-10",
                    "description": "<p>Runs direct on solar.</p>",
                    "short_description": "Batteryless inverter",
                    "permalink": "https://enertechups.com/product/batteryless-solar-hybrid-inverter/",
                    "images": [{"src": "https://enertechups.com/wp-content/uploads/bl.png"}],
                    "categories": [{"id": 123}],
                    "attributes": [],
                    "price": "150000",
                    "stock_status": "instock",
                },
                {
                    "id": 3920,
                    "name": "Batteryless Pro Specific PDF Model",
                    "slug": "batteryless-pro-specific",
                    "sku": "ET-BL-20",
                    "description": '<p>Spec sheet <a href="https://enertechups.com/wp-content/uploads/et-bl-20.pdf">Brochure</a></p>',
                    "short_description": "",
                    "permalink": "https://enertechups.com/product/batteryless-pro-specific/",
                    "images": [],
                    "categories": [{"id": 123}],
                    "attributes": [],
                    "price": "220000",
                    "stock_status": "instock",
                },
            ],
            "wc/store/v1/products": [],
            "wp/v2/media": [],
            "wp/v2/product": [],
            "wp/v2/product_cat": [],
        },
        # Second sync drops PDFs from incoming WordPress payloads — existing associations MUST survive.
        {
            "wc/v3/products/categories": [
                {"id": 123, "name": "Batteryless Solar Hybrid Inverter", "slug": "batteryless-solar-hybrid-inverter", "description": ""},
            ],
            "wc/v3/products": [
                {
                    "id": 3919,
                    "name": "Batteryless Gridless Solar Hybrid Inverter",
                    "slug": "batteryless-gridless-solar-hybrid-inverter",
                    "sku": "ET-BL-10",
                    "description": "<p>Updated description without PDF link.</p>",
                    "short_description": "Batteryless inverter",
                    "permalink": "https://enertechups.com/product/batteryless-solar-hybrid-inverter/",
                    "images": [],
                    "categories": [{"id": 123}],
                    "attributes": [],
                    "price": "150000",
                    "stock_status": "instock",
                },
                {
                    "id": 3920,
                    "name": "Batteryless Pro Specific PDF Model",
                    "slug": "batteryless-pro-specific",
                    "sku": "ET-BL-20",
                    "description": "<p>Updated text without PDF.</p>",
                    "short_description": "",
                    "permalink": "https://enertechups.com/product/batteryless-pro-specific/",
                    "images": [],
                    "categories": [{"id": 123}],
                    "attributes": [],
                    "price": "220000",
                    "stock_status": "instock",
                },
            ],
            "wc/store/v1/products": [],
            "wp/v2/media": [],
            "wp/v2/product": [],
            "wp/v2/product_cat": [],
        },
    ]

    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    current_dataset = sync_datasets[0]
    monkeypatch.setattr(wordpress_api, "_fetch_all", lambda path, **_kwargs: current_dataset.get(path, []))

    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="sync-admin", role="super_admin", is_active=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "sync-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    # 1. Run initial sync
    sync1 = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert sync1.status_code == 200, sync1.text
    assert sync1.json()["documents_linked"] == 1
    assert client.get("/api/v1/catalogue/categories").json() == []
    assert client.get("/api/v1/catalogue/products").json()["total"] == 0
    assert client.get("/api/v1/catalogue/products/batteryless-pro-specific").status_code == 404
    base = "/api/v1/admin/catalogue"
    items = client.get(f"{base}/products?assignment=unassigned").json()["items"]
    ids = [item["id"] for item in items]
    assert len(ids) == 2
    family_url = "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"
    second_url = "https://cdn.example.test/secondary.pdf"
    primary = publish_collection(client, "curated-batteryless", ids, family_url)
    secondary = publish_collection(client, "secondary-batteryless", ids, second_url)
    assert client.get(f"{base}/products?assignment=unassigned").json()["total"] == 0
    home_path = "/api/v1/admin/app-config/home"
    config = {"featured_product_category_ids": [secondary], "featured_products_title": "Featured series"}
    assert client.put(home_path, json=config).status_code == 200
    assert client.post(f"{home_path}/publish").status_code == 200
    assert client.get("/api/v1/app/config").json()["home"]["featured_product_category_ids"] == [secondary]
    tag_id = client.get(f"{base}/categories?kind=wp_tag").json()[0]["id"]
    for key in ["featured_category_ids", "featured_product_category_ids"]:
        assert client.put(home_path, json={key: [tag_id]}).status_code == 200
        assert client.post(f"{home_path}/publish").status_code == 422
    secondary_path = f"{base}/categories/{secondary}/products"
    options = client.get(secondary_path).json()
    assert all(row["checked"] for row in options["products"])
    assert len(options["tags"]) == 1
    assert client.put(secondary_path, json={"product_ids": [], "previous_product_ids": []}).status_code == 409

    # 2. Verify CMS admin API returns resolved PDFs (inherited + product-specific)
    cms_cats = client.get("/api/v1/admin/catalogue/categories").json()
    assert {row["catalog_pdf_url"] for row in cms_cats} == {family_url, second_url}

    cms_prods = {p["slug"]: p for p in client.get("/api/v1/admin/catalogue/products").json()["items"]}
    assert cms_prods["batteryless-gridless-solar-hybrid-inverter"]["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"
    assert cms_prods["batteryless-gridless-solar-hybrid-inverter"]["catalog_pdf_source"] == "category"
    assert cms_prods["batteryless-pro-specific"]["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/et-bl-20.pdf"
    assert cms_prods["batteryless-pro-specific"]["catalog_pdf_source"] == "product"

    # 3. Verify Mobile/Public API returns inherited + specific PDFs
    pub_list = {p["slug"]: p for p in client.get("/api/v1/catalogue/products").json()["items"]}
    assert pub_list["batteryless-gridless-solar-hybrid-inverter"]["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"
    assert pub_list["batteryless-gridless-solar-hybrid-inverter"]["documents"][0]["url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"
    pub_detail = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert pub_detail["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"

    assert [d["url"] for d in pub_detail["documents"]] == [family_url, second_url]
    context = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter?category=secondary-batteryless").json()
    assert context["category_ids"] == [secondary, primary]
    assert [d["url"] for d in context["documents"]] == [second_url, family_url]
    page = client.get(f"/api/v1/catalogue/products?category_ids={secondary},{primary}").json()
    assert page["total"] == 2
    own = pub_list["batteryless-pro-specific"]
    assert [d["url"] for d in own["documents"]] == [own["catalog_pdf_url"], family_url, second_url]

    # 4. Re-run sync where WP omits PDFs -> existing product & category PDF associations MUST remain intact!
    current_dataset = sync_datasets[1]
    sync2 = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert sync2.status_code == 200, sync2.text
    assert sync2.json()["documents_linked"] == 2
    pub_after = client.get("/api/v1/catalogue/products/batteryless-pro-specific").json()
    assert pub_after["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/et-bl-20.pdf"
    pub_inherited_after = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert pub_inherited_after["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"

    # 5. CMS admin override on collection PDF persists across future WP syncs
    cms_override = client.put("/api/v1/admin/catalogue/category-catalogues", json={
        "category_key": "curated-batteryless",
        "title": "CMS Curated Batteryless Catalogue",
        "catalog_pdf_url": "https://cdn.example.test/enertech-public/cms/batteryless-v2.pdf",
    })
    assert cms_override.status_code == 200, cms_override.text
    current_dataset = sync_datasets[0]
    assert client.post("/api/v1/admin/integrations/wordpress/sync").status_code == 200
    pub_cms_override = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert pub_cms_override["catalog_pdf_url"] == "https://cdn.example.test/enertech-public/cms/batteryless-v2.pdf"
    assert pub_cms_override["documents"][0]["title"] == "CMS Curated Batteryless Catalogue"

    assert client.patch(f"{base}/categories/{secondary}", json={"catalog_pdf_url": pub_cms_override["catalog_pdf_url"]}).status_code == 200
    duplicate = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert len(duplicate["documents"]) == 1
    assert client.patch(f"{base}/categories/{secondary}", json={"catalog_pdf_url": second_url}).status_code == 200

    # Removing the primary promotes the secondary. A last removal returns imported products to staging.
    assert client.put(f"{base}/categories/{primary}/products", json={"product_ids": []}).status_code == 200
    detail = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert detail["category_ids"] == [secondary]
    assert detail["catalog_pdf_url"] == second_url
    assert client.put(secondary_path, json={"product_ids": []}).status_code == 200
    assert client.get("/api/v1/catalogue/products").json()["total"] == 0
    assert client.get(f"{base}/products?assignment=unassigned").json()["total"] == 2



def test_wordpress_sync_html_fallback_and_telemetry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://enertechups.com/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="",
        wordpress_documents_path="wp/v2/media",
        wordpress_wp_products_path="",
        wordpress_consumer_key="ck_test",
        wordpress_consumer_secret="cs_test",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
        wordpress_source_documents_field="",
        wordpress_html_fallback_enabled=True,
    )
    dataset = {
        "wc/v3/products/categories": [
            {"id": 201, "name": "Industrial UPS", "slug": "industrial-ups", "description": ""},
            {"id": 202, "name": "Voltage Stabilizers", "slug": "voltage-stabilizers", "description": ""},
        ],
        "wc/v3/products": [
            {
                "id": 5001,
                "name": "100 KVA Industrial UPS",
                "slug": "100-kva-industrial-ups",
                "sku": "ET-UPS-100",
                "description": "<p>High reliability industrial UPS.</p>",
                "short_description": "",
                "permalink": "https://enertechups.com/product/100-kva-industrial-ups/",
                "images": [],
                "categories": [{"id": 201}],
                "attributes": [],
                "price": "776200",
                "stock_status": "instock",
            },
            {
                "id": 5002,
                "name": "10KVA Voltage Stabilizer",
                "slug": "10kva-voltage-stabilizer",
                "sku": "ET-VS-10",
                "description": "<p>Servo stabilizer.</p>",
                "short_description": "",
                "permalink": "https://enertechups.com/product/10kva-voltage-stabilizer/",
                "images": [],
                "categories": [{"id": 202}],
                "attributes": [],
                "price": "45500",
                "stock_status": "instock",
            },
        ],
        "wp/v2/media": [],
    }
    html_pages = {
        "https://enertechups.com/product-category/industrial-ups/": (
            "<main><a href='http://enertechups.com/wp-content/uploads/industrial-ups-family.pdf'>Family Catalogue</a></main>"
        ),
        "https://enertechups.com/product/100-kva-industrial-ups/": (
            "<header><a href='/wp-content/uploads/header.pdf'>Header</a></header>"
            "<main><a href='/wp-content/uploads/100kva-industrial-ups.pdf'>Download Brochure</a></main>"
        ),
        "https://enertechups.com/product/10kva-voltage-stabilizer/": (
            "<header><a href='/wp-content/uploads/header.pdf'>Header</a></header>"
            "<main><p>Details only, no brochure uploaded.</p></main>"
        ),
    }

    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    monkeypatch.setattr(wordpress_api, "_fetch_all", lambda path, **_kwargs: dataset.get(path, []))
    monkeypatch.setattr(wordpress_api, "_fetch_html_page", lambda url, **_kwargs: html_pages.get(url, ""))

    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="html-admin", role="super_admin", is_active=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "html-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    resp = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched_by_html"] == 1
    assert client.get("/api/v1/admin/catalogue/category-catalogues").json() == []
    items = client.get("/api/v1/admin/catalogue/products").json()["items"]
    publish_collection(client, "curated-ups", [p["id"] for p in items])
    assert body["documents_linked"] == 1

    ups_detail = client.get("/api/v1/catalogue/products/100-kva-industrial-ups").json()
    assert ups_detail["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/100kva-industrial-ups.pdf"

    stabilizer_detail = client.get("/api/v1/catalogue/products/10kva-voltage-stabilizer").json()
    assert stabilizer_detail["catalog_pdf_url"] is None
    assert stabilizer_detail["documents"] == []


def test_woocommerce_store_fallback_preserves_existing_descriptions_and_specs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://enertechups.com/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="wc/store/v1/products",
        wordpress_documents_path="",
        wordpress_wp_products_path="",
        wordpress_consumer_key="ck_test",
        wordpress_consumer_secret="cs_test",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
        wordpress_source_documents_field="",
        wordpress_html_fallback_enabled=False,
    )
    use_store_fallback = False

    def fake_fetch(path: str, **_kwargs):
        if path == "wc/v3/products":
            if use_store_fallback:
                raise HTTPException(status_code=502, detail="WordPress returned HTTP 503 from wc/v3/products")
            return [
                {
                    "id": 6001,
                    "name": "30 KVA Industrial UPS",
                    "slug": "30-kva-industrial-ups",
                    "sku": "ET-IND-30",
                    "short_description": "True online double conversion UPS",
                    "description": '<p>Heavy duty UPS. <a href="https://enertechups.com/wp-content/uploads/30kva-ups.pdf">Brochure</a></p>',
                    "permalink": "https://enertechups.com/shop/30-kva-industrial-ups/",
                    "images": [{"src": "https://enertechups.com/wp-content/uploads/30kva.png"}],
                    "categories": [{"id": 301, "name": "Industrial UPS"}],
                    "attributes": [{"name": "Capacity", "options": ["30 kVA"]}],
                    "price": "450000",
                    "stock_status": "instock",
                }
            ]
        if path == "wc/v3/products/categories":
            return [{"id": 301, "name": "Industrial UPS", "slug": "industrial-ups", "description": ""}]
        if path == "wc/store/v1/products":
            return [
                {
                    "id": 6001,
                    "name": "30 KVA Industrial UPS",
                    "slug": "30-kva-industrial-ups",
                    "sku": "",
                    "short_description": "",
                    "description": "",
                    "permalink": "https://enertechups.com/shop/30-kva-industrial-ups/",
                    "images": [],
                    "categories": [{"id": 301, "name": "Industrial UPS", "slug": "industrial-ups"}],
                    "prices": {"price": "45000000", "currency_code": "INR", "currency_minor_unit": 2},
                    "is_in_stock": True,
                }
            ]
        return []

    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    monkeypatch.setattr(wordpress_api, "_fetch_all", fake_fetch)

    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="fallback-admin", role="super_admin", is_active=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "fallback-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    assert client.post("/api/v1/admin/integrations/wordpress/sync").status_code == 200
    items = client.get("/api/v1/admin/catalogue/products").json()["items"]
    publish_collection(client, "curated-ups", [p["id"] for p in items])
    use_store_fallback = True
    fallback_resp = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert fallback_resp.status_code == 200, fallback_resp.text
    assert fallback_resp.json()["fallback_used"] == "wc/store/v1/products"

    detail = client.get("/api/v1/catalogue/products/30-kva-industrial-ups").json()
    assert detail["model_code"] == "ET-IND-30"
    assert detail["summary"] == "True online double conversion UPS"
    assert "Heavy duty UPS" in detail["description"]
    assert detail["specifications"] == {"Capacity": ["30 kVA"]}
    assert detail["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/30kva-ups.pdf"


def test_cms_overrides_and_smart_category_selection_survive_wordpress_sync(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://enertechups.com/wp-json",
        wordpress_products_path="wc/v3/products",
        wordpress_categories_path="wc/v3/products/categories",
        wordpress_store_products_path="",
        wordpress_documents_path="",
        wordpress_wp_products_path="",
        wordpress_consumer_key="ck_test",
        wordpress_consumer_secret="cs_test",
        wordpress_source_title_field="name",
        wordpress_source_slug_field="slug",
        wordpress_source_summary_field="short_description",
        wordpress_source_description_field="description",
        wordpress_source_model_field="sku",
        wordpress_source_image_field="images.0.src",
        wordpress_source_specifications_field="attributes",
        wordpress_source_applications_field="",
        wordpress_source_features_field="",
        wordpress_source_documents_field="",
        wordpress_html_fallback_enabled=False,
    )
    dataset = {
        "wc/v3/products/categories": [
            {"id": 10, "name": "Power Products", "slug": "power-products", "description": ""},
            {"id": 11, "name": "Servo Stabilizer", "slug": "servo-stabilizer", "description": ""},
            {"id": 12, "name": "Empty SEO Tag", "slug": "empty-seo-tag", "description": "", "count": 0},
        ],
        "wc/v3/products": [
            {
                "id": 7001,
                "name": "60 KVA Servo Voltage Stabilizer",
                "slug": "60-kva-servo-stabilizer",
                "sku": "ET-SVS-60",
                "description": '<p>Stabilizer <a href="https://enertechups.com/wp-content/uploads/wrong.pdf">Wrong PDF</a></p>',
                "short_description": "",
                "permalink": "https://enertechups.com/shop/60-kva-servo-stabilizer/",
                "images": [],
                "categories": [{"id": 10}, {"id": 11}],
                "attributes": [],
                "price": "50000",
                "stock_status": "instock",
            },
            {
                "id": 7002,
                "name": "30 KVA UPS",
                "slug": "30-kva-ups-7002",
                "sku": "ET-UPS-30",
                "description": "<p>Online UPS</p>",
                "short_description": "",
                "permalink": "https://enertechups.com/shop/30-kva-ups-7002/",
                "images": [],
                "categories": [{"id": 10}],
                "attributes": [],
                "price": "40000",
                "stock_status": "instock",
            },
        ],
    }
    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    monkeypatch.setattr(wordpress_api, "_fetch_all", lambda path, **_kwargs: dataset.get(path, []))
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="override-admin", role="super_admin", is_active=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "override-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    first = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert first.status_code == 200, first.text

    # Empty SEO category imported unpublished and omitted from public catalogue categories.
    cats_admin = {row["slug"]: row for row in client.get("/api/v1/admin/catalogue/categories?kind=wp_tag").json()}
    assert cats_admin["empty-seo-tag"]["is_published"] is False
    assert cats_admin["empty-seo-tag"]["product_count"] == 0
    public_slugs = {row["slug"] for row in client.get("/api/v1/catalogue/categories").json()}
    assert "empty-seo-tag" not in public_slugs

    # Smart default picks specific leaf "servo-stabilizer" over broad "power-products".
    prods_admin = {row["slug"]: row for row in client.get("/api/v1/admin/catalogue/products").json()["items"]}
    svs = prods_admin["60-kva-servo-stabilizer"]
    assert svs["category_id"] == cats_admin["servo-stabilizer"]["id"]

    curated = publish_collection(client, "curated-servo", [svs["id"]], "https://cdn.example.test/enertech-public/cms/servo.pdf")
    assert client.delete(f"/api/v1/admin/catalogue/products/{svs['id']}/pdf").status_code == 200

    # Re-assign 30 KVA UPS via CMS override + verify bulk category endpoint & summary.
    ups = prods_admin["30-kva-ups-7002"]
    assert client.put(
        f"/api/v1/admin/catalogue/products/{ups['id']}/categories",
        json={"category_id": curated, "category_ids": [curated]},
    ).status_code == 200

    # Re-sync from WordPress -> CMS hidden category stays hidden, cleared PDF stays cleared (inheriting servo.pdf), category override stays intact!
    second = client.post("/api/v1/admin/integrations/wordpress/sync")
    assert second.status_code == 200, second.text
    assert second.json()["cms_preserved_category_products"] >= 1
    assert second.json()["cms_preserved_pdf_products"] >= 1

    cats_after = {row["slug"]: row for row in client.get("/api/v1/admin/catalogue/categories?kind=wp_tag").json()}
    assert cats_after["power-products"]["is_published"] is False
    svs_after = client.get("/api/v1/catalogue/products/60-kva-servo-stabilizer").json()
    assert svs_after["catalog_pdf_url"] == "https://cdn.example.test/enertech-public/cms/servo.pdf"
    ups_after = client.get("/api/v1/catalogue/products/30-kva-ups-7002").json()
    assert ups_after["category_ids"] == [curated]

    summary = client.get("/api/v1/admin/catalogue/summary")
    assert summary.status_code == 200
    assert summary.json()["products_total"] == 2
    assert summary.json()["categories_empty"] == 0
    assert summary.json()["products_category_overridden"] == 2


def test_service_request_accepts_attachments(client: TestClient) -> None:
    identity = Identity("customer-img", "img@example.test", "Img Customer", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: identity
    res = client.post("/api/v1/requests/service", json={
        "product_model": "HTXi-100",
        "problem_category": "alarm",
        "description": "Display showing battery low warning after outage.",
        "service_location": "Pune, 411001",
        "attachments": ["https://storage.example.test/enertech-public/service-requests/customer-img/photo1.jpg"],
    })
    assert res.status_code == 201, res.text
    assert res.json()["payload"]["attachments"] == [
        "https://storage.example.test/enertech-public/service-requests/customer-img/photo1.jpg"
    ]


def test_warranty_and_amc_requests_are_owned_and_reviewable(client: TestClient) -> None:
    customer = Identity("customer-coverage", "coverage@example.test", "Customer", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: customer
    warranty = {
        "customer_name": "Customer One", "email": "coverage@example.test",
        "mobile_number": "+919876543210", "purchase_date": "2026-01-15",
        "serial_number": "ET-100-001",
    }
    assert client.post("/api/v1/requests/warranty", json={**warranty, "email": "other@example.test"}).status_code == 422
    created_warranty = client.post("/api/v1/requests/warranty", json=warranty)
    assert created_warranty.status_code == 201, created_warranty.text
    assert created_warranty.json()["kind"] == "warranty"
    assert created_warranty.json()["status"] == "submitted"
    assert client.post("/api/v1/requests/amc", json={
        "serial_number": "ET-100-001", "location": "Pune", "purchase_date": "2026-01-15",
    }).status_code == 201
    assert [row["kind"] for row in client.get("/api/v1/requests").json()] == ["amc", "warranty"]

    other = Identity("other-customer", "other@example.test", "Other", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: other
    assert client.get("/api/v1/requests").json() == []

    admin = Identity("coverage-admin", "admin@example.test", "Admin", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: admin
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="coverage-admin", role="super_admin", is_active=True))
        session.commit()
    rows = client.get("/api/v1/admin/requests?kind=warranty")
    assert rows.status_code == 200
    assert len(rows.json()) == 1
    changed = client.patch(f"/api/v1/admin/requests/{created_warranty.json()['id']}", json={"status": "in_review"})
    assert changed.status_code == 200, changed.text


def test_faq_media_stays_in_draft_until_published(client: TestClient) -> None:
    admin = Identity("faq-admin", "faq@example.test", "Admin", {"email_verified": True})
    app.dependency_overrides[get_current_identity] = lambda: admin
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="faq-admin", role="super_admin", is_active=True))
        session.commit()
    body = {
        "slug": "battery-care", "title": "How do I care for batteries?",
        "category": "Maintenance", "answer": "# Battery care\n- Check **terminals** monthly.",
        "image_urls": ["https://cdn.example.test/faq/battery.jpg"],
        "video_urls": ["https://cdn.example.test/faq/battery.mp4", "https://www.youtube.com/watch?v=example"],
        "source_reference": "Approved service guide", "sort_order": 1,
    }
    created = client.post("/api/v1/admin/knowledge", json=body)
    assert created.status_code == 201, created.text
    article_id = created.json()["id"]
    assert client.get("/api/v1/knowledge").json() == []
    published = client.post(f"/api/v1/admin/knowledge/{article_id}/publish")
    assert published.status_code == 200, published.text
    public = client.get("/api/v1/knowledge").json()[0]
    assert public["image_urls"] == body["image_urls"]
    assert public["video_urls"] == body["video_urls"]
    assert client.patch(f"/api/v1/admin/knowledge/{article_id}", json={"answer": "# Updated care\n- New advice"}).status_code == 200
    assert client.get("/api/v1/knowledge").json()[0]["answer"] == body["answer"]
    assert client.post(f"/api/v1/admin/knowledge/{article_id}/publish").status_code == 200
    assert client.get("/api/v1/knowledge").json()[0]["answer"] == "# Updated care\n- New advice"
