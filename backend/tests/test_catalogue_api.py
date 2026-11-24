from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.router as api_router
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models import Product, ProductCategory


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


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "q=" + ("x" * 121)])
def test_invalid_catalogue_parameters_are_rejected(client: TestClient, query: str) -> None:
    assert client.get(f"/api/v1/catalogue/products?{query}").status_code == 422
