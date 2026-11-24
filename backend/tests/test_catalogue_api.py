from collections.abc import Iterator
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.router as api_router
import app.core.auth as auth
from app.core.auth import Identity, get_current_identity
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import AdminAccount, AppConfig, ContactInquiry, CustomerRequest, Product, ProductCategory


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
