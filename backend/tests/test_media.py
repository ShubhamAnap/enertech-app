import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api import customer_requests, media
from app.core.auth import AdminIdentity, Identity


def test_media_upload_uses_async_storage_request(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)

    class AsyncStorageClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"id": "enertech-public", "public": True})

        async def put(self, url, **kwargs):
            assert url.startswith("https://storage.example.test/storage/v1/object/enertech-public/cms/")
            assert kwargs["headers"]["Content-Type"] == "image/png"
            return httpx.Response(200)

    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **_kwargs: AsyncStorageClient())
    session = Mock()
    upload = UploadFile(filename="company-logo.png", file=BytesIO(b"\x89PNG\r\n\x1a\ncontent"))
    admin = AdminIdentity(uid="cms-admin", email="admin@example.test", name="CMS Admin", role="super_admin")

    result = asyncio.run(media.upload_media(upload, session=session, admin=admin))

    assert result.content_type == "image/png"
    assert result.size_bytes == len(b"\x89PNG\r\n\x1a\ncontent")
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_media_upload_rejects_files_over_the_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(media, "get_settings", lambda: SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    ))
    upload = UploadFile(filename="too-large.png", file=BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * media.MAX_FILE_BYTES))
    admin = AdminIdentity(uid="cms-admin", email="admin@example.test", name="CMS Admin", role="super_admin")

    with pytest.raises(HTTPException) as error:
        asyncio.run(media.upload_media(upload, session=Mock(), admin=admin))

    assert error.value.status_code == 413


def test_media_upload_accepts_pdf_brochures(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)

    class AsyncStorageClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"id": "enertech-public", "public": True})

        async def put(self, url, **kwargs):
            assert url.endswith(".pdf")
            assert kwargs["headers"]["Content-Type"] == "application/pdf"
            return httpx.Response(200)

    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **_kwargs: AsyncStorageClient())
    session = Mock()
    upload = UploadFile(filename="brochure.pdf", file=BytesIO(b"%PDF-1.7\ncontent"))
    admin = AdminIdentity(uid="cms-admin", email="admin@example.test", name="CMS Admin", role="super_admin")

    result = asyncio.run(media.upload_media(upload, session=session, admin=admin))
    assert result.content_type == "application/pdf"
    assert str(result.url).endswith(".pdf")


def test_faq_video_upload_accepts_mp4_and_rejects_other_files(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)

    class AsyncStorageClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"public": True})

        async def put(self, url, **kwargs):
            assert "/cms/faq-videos/" in url
            assert kwargs["headers"]["Content-Type"] == "video/mp4"
            return httpx.Response(200)

    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **_kwargs: AsyncStorageClient())
    admin = AdminIdentity(uid="cms-admin", email="admin@example.test", name="CMS Admin", role="super_admin")
    payload = b"\x00\x00\x00\x18ftypisomvideo"
    result = asyncio.run(media.upload_faq_video(
        UploadFile(filename="faq.mp4", file=BytesIO(payload)), session=Mock(), admin=admin,
    ))
    assert result.content_type == "video/mp4"
    with pytest.raises(HTTPException) as error:
        asyncio.run(media.upload_faq_video(
            UploadFile(filename="fake.mp4", file=BytesIO(b"not a video")), session=Mock(), admin=admin,
        ))
    assert error.value.status_code == 415


def test_media_upload_auto_creates_missing_public_bucket(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)

    class AsyncStorageClient:
        calls: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def put(self, url, **kwargs):
            self.calls.append(f"PUT:{url}")
            if len([c for c in self.calls if c.startswith("PUT:")]) == 1:
                return httpx.Response(404, json={"statusCode": "404", "error": "Bucket not found", "message": "Bucket not found"})
            return httpx.Response(200)

        async def post(self, url, **kwargs):
            self.calls.append(f"POST:{url}")
            assert url == "https://storage.example.test/storage/v1/bucket"
            assert kwargs["json"] == {"id": "enertech-public", "name": "enertech-public", "public": True}
            return httpx.Response(200, json={"name": "enertech-public"})

    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **_kwargs: AsyncStorageClient())
    session = Mock()
    upload = UploadFile(filename="brochure.pdf", file=BytesIO(b"%PDF-1.7\ncontent"))
    admin = AdminIdentity(uid="cms-admin", email="admin@example.test", name="CMS Admin", role="super_admin")

    result = asyncio.run(media.upload_media(upload, session=session, admin=admin))
    assert result.bucket == "enertech-public"
    assert AsyncStorageClient.calls == [
        AsyncStorageClient.calls[0],
        "POST:https://storage.example.test/storage/v1/bucket",
        AsyncStorageClient.calls[2],
    ]


def test_customer_service_photo_upload_accepts_image_and_rejects_pdf(monkeypatch) -> None:
    settings = SimpleNamespace(
        supabase_url="https://storage.example.test",
        supabase_service_role_key="test-server-key",
        supabase_public_media_bucket="enertech-public",
    )
    monkeypatch.setattr(media, "get_settings", lambda: settings)
    monkeypatch.setattr(customer_requests, "get_settings", lambda: settings)

    class AsyncStorageClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, url, **kwargs):
            return httpx.Response(200, json={"id": "enertech-public", "public": True})

        async def put(self, url, **kwargs):
            assert "/service-requests/cust-1/" in url
            assert kwargs["headers"]["Content-Type"] == "image/jpeg"
            return httpx.Response(200)

    monkeypatch.setattr(media.httpx, "AsyncClient", lambda **_kwargs: AsyncStorageClient())
    session = Mock()
    session.scalar.return_value = 0
    identity = Identity(uid="cust-1", email="cust@example.test", name="Customer", claims={"email_verified": True})

    jpg_upload = UploadFile(filename="fault.jpg", file=BytesIO(b"\xff\xd8\xff\xe0test-jpeg-bytes"))
    result = asyncio.run(customer_requests.upload_service_request_photo(jpg_upload, identity=identity, session=session))
    assert result.content_type == "image/jpeg"
    assert result.path.startswith("service-requests/cust-1/")

    pdf_upload = UploadFile(filename="doc.pdf", file=BytesIO(b"%PDF-1.7\nnot-an-image"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(customer_requests.upload_service_request_photo(pdf_upload, identity=identity, session=session))
    assert error.value.status_code == 415
