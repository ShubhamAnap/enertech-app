from collections.abc import Iterator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
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
        expected_category_ids = {str(primary.id), str(secondary.id), str(hidden.id)}

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


def test_woocommerce_catalogue_rows_cannot_be_edited_published_or_deleted_in_cms(client: TestClient) -> None:
    category_id, product_id = uuid4(), uuid4()
    with Session(api_router.engine) as session:
        session.add(AdminAccount(firebase_uid="catalogue-admin", role="admin", is_active=True))
        session.add(ProductCategory(id=category_id, slug="wp-read-only", name="WooCommerce collection", wordpress_source_id="wp-category-90", is_published=True))
        session.add(Product(id=product_id, category_id=category_id, slug="wp-read-only-product", name="WooCommerce product", wordpress_source_id="wp-product-90", is_published=True))
        session.commit()
    app.dependency_overrides[get_current_identity] = lambda: Identity(
        "catalogue-admin", "admin@example.test", "Admin", {"email_verified": True}
    )

    assert client.patch(f"/api/v1/admin/catalogue/products/{product_id}", json={"name": "Local override"}).status_code == 409
    assert client.post(f"/api/v1/admin/catalogue/products/{product_id}/publish").status_code == 409
    assert client.delete(f"/api/v1/admin/catalogue/products/{product_id}").status_code == 409
    assert client.patch(f"/api/v1/admin/catalogue/categories/{category_id}", json={"name": "Local override"}).status_code == 409
    assert client.post(f"/api/v1/admin/catalogue/categories/{category_id}/publish").status_code == 409
    assert client.delete(f"/api/v1/admin/catalogue/categories/{category_id}").status_code == 409


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
        wordpress_wp_categories_path="wp/v2/product_cat",
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
    assert sync1.json()["category_catalogues_synced"] == 1
    assert sync1.json()["documents_linked"] == 2

    # 2. Verify CMS admin API returns resolved PDFs (inherited + product-specific)
    cms_cats = client.get("/api/v1/admin/catalogue/categories").json()
    assert cms_cats[0]["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/batteryless-family.pdf"

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
        "category_key": "batteryless-solar-hybrid-inverter",
        "title": "CMS Curated Batteryless Catalogue",
        "catalog_pdf_url": "https://cdn.example.test/enertech-public/cms/batteryless-v2.pdf",
    })
    assert cms_override.status_code == 200, cms_override.text
    current_dataset = sync_datasets[0]
    assert client.post("/api/v1/admin/integrations/wordpress/sync").status_code == 200
    pub_cms_override = client.get("/api/v1/catalogue/products/batteryless-gridless-solar-hybrid-inverter").json()
    assert pub_cms_override["catalog_pdf_url"] == "https://cdn.example.test/enertech-public/cms/batteryless-v2.pdf"
    assert pub_cms_override["documents"][0]["title"] == "CMS Curated Batteryless Catalogue"


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
        wordpress_wp_categories_path="",
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
    assert body["category_catalogues_synced"] == 1
    assert body["documents_linked"] == 1

    ups_detail = client.get("/api/v1/catalogue/products/100-kva-industrial-ups").json()
    assert ups_detail["catalog_pdf_url"] == "https://enertechups.com/wp-content/uploads/100kva-industrial-ups.pdf"

    stabilizer_detail = client.get("/api/v1/catalogue/products/10kva-voltage-stabilizer").json()
    assert stabilizer_detail["catalog_pdf_url"] is None
    assert stabilizer_detail["documents"] == []
