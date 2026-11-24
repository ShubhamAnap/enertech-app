import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.api import media
from app.core.auth import AdminIdentity


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
