from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import unescape
from html.parser import HTMLParser
import json
import logging
import re
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.core.config import get_settings
from app.db.session import get_session
from app.models import AuditEvent, Product, ProductCategory, ProductCategoryCatalogue
from app.services.catalogue_documents import (
    load_category_catalogue_lookup,
    normalize_pdf_documents,
    resolve_product_documents_for_model,
)

router = APIRouter(prefix="/admin/integrations/wordpress", tags=["wordpress integration"])
logger = logging.getLogger(__name__)
ROLES = ("content_editor", "admin", "super_admin")
_REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; EnerTechSync/1.0)",
}
_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}
_MAX_REDIRECTS = 3
_HTML_STRIP_SECTIONS_RE = re.compile(
    r"<(?:header|nav|footer)\b[^>]*>.*?</(?:header|nav|footer)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_ANCHOR_RE = re.compile(
    r"<a\b([^>]*)href=[\"']([^\"']+)[\"']([^>]*)>(.*?)</a>",
    flags=re.IGNORECASE | re.DOTALL,
)
_DOWNLOAD_HINT_RE = re.compile(
    r"brochure|catalogue|catalog|datasheet|data\s*sheet|download|manual|spec(?:ification)?|pdf",
    flags=re.IGNORECASE,
)


class WordPressImport(BaseModel):
    source_id: str = Field(min_length=1, max_length=160)
    category_id: UUID


class _TextOnly(HTMLParser):
    _BLOCK_TAGS = {
        "address", "article", "blockquote", "br", "dd", "div", "dl", "dt",
        "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
        "li", "ol", "p", "section", "table", "td", "th", "tr", "ul",
    }

    def __init__(self, *, preserve_blocks: bool = False) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.preserve_blocks = preserve_blocks

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.preserve_blocks and tag in self._BLOCK_TAGS:
            self.parts.append("\n• " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if self.preserve_blocks and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _field(record: dict[str, Any], path: str, default: Any = None) -> Any:
    value: Any = record
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdecimal():
            index = int(part)
            value = value[index] if index < len(value) else None
        else:
            return default
    return default if value is None else value


def _plain(value: Any, limit: int = 500, *, preserve_blocks: bool = False) -> str:
    parser = _TextOnly(preserve_blocks=preserve_blocks)
    parser.feed(str(value or ""))
    text = "".join(parser.parts) if preserve_blocks else " ".join(parser.parts)
    for _ in range(3):
        decoded = unescape(text)
        if decoded == text:
            break
        text = decoded
    if preserve_blocks:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line)[:limit]
    return " ".join(text.split())[:limit]


def _string_list(value: Any, limit: int = 32) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("options", item.get("name", item.get("value", "")))
        values = item if isinstance(item, list) else [item]
        for entry in values:
            text = _plain(entry, 180)
            if text:
                result.append(text)
            if len(result) >= limit:
                return result
    return result


def _image_url(value: Any, *, site_origin: str = "") -> str | None:
    candidate = value.get("url", value.get("src")) if isinstance(value, dict) else value
    return _https_url(candidate, site_origin=site_origin)


def _specifications(value: Any) -> dict[str, str | list[str]]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = (
            (str(item.get("name", "")), item.get("options", item.get("value", "")))
            for item in value
            if isinstance(item, dict)
        )
    else:
        return {}
    result: dict[str, str | list[str]] = {}
    for key, raw in items:
        label = _plain(key, 80)
        value_text = _string_list(raw, 12) if isinstance(raw, list) else _plain(raw, 500)
        if label and value_text:
            result[label] = value_text
        if len(result) >= 60:
            break
    return result


def _normalize_wp_base_url(raw_url: str, app_env: str = "production") -> str:
    base = raw_url.strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Set the WordPress REST URL and WooCommerce product routes in the API environment")
    parsed = urlparse(base)
    if parsed.scheme != "https" and app_env != "local":
        raise HTTPException(status_code=503, detail="WordPress must use HTTPS outside local development")
    if not parsed.netloc:
        raise HTTPException(status_code=503, detail="WORDPRESS_API_BASE_URL must be a valid URL")
    if "wp-json" not in parsed.path and "rest_route" not in base and parsed.path in ("", "/"):
        base = f"{base}/wp-json"
    return base


def _site_origin(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _configured_rest_url(path: str) -> str:
    settings = get_settings()
    app_env = str(getattr(settings, "app_env", "production")).lower()
    base = _normalize_wp_base_url(getattr(settings, "wordpress_api_base_url", ""), app_env=app_env)
    clean_path = path.strip("/")
    if not clean_path:
        raise HTTPException(status_code=503, detail="Set the WordPress REST URL and WooCommerce product routes in the API environment")
    return f"{base}/{clean_path}"


def _sanitize_url_for_log(url: str) -> str:
    parts = urlsplit(url)
    filtered_query = [
        (k, "***" if k in {"consumer_key", "consumer_secret"} else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(filtered_query), ""))


def _sanitize_log_snippet(raw_text: str, *, secrets: tuple[str, ...] = (), limit: int = 300) -> str:
    cleaned = " ".join(raw_text.replace("\ufeff", "").split())
    for secret in secrets:
        if secret and len(secret) >= 4:
            cleaned = cleaned.replace(secret, "***")
    return cleaned[:limit]


def _host_group(host: str) -> str:
    normalized = host.lower().split(":", 1)[0]
    return normalized[4:] if normalized.startswith("www.") else normalized


def _safe_redirect_url(current_url: str, location: str, *, app_env: str = "production") -> str | None:
    if not location:
        return None
    target = urljoin(current_url, location.strip())
    cur_parsed = urlparse(current_url)
    tgt_parsed = urlparse(target)
    if tgt_parsed.scheme not in {"http", "https"}:
        return None
    if tgt_parsed.scheme == "http" and app_env != "local":
        # Upgrade HTTP redirect on same site to HTTPS cleanly.
        target = f"https://{target[7:]}"
    if _host_group(cur_parsed.netloc) != _host_group(tgt_parsed.netloc):
        return None
    return target


def _safe_json(response: httpx.Response, *, expect_list: bool = False) -> Any:
    raw_bytes = response.content if hasattr(response, "content") and response.content is not None else response.text.encode("utf-8", errors="replace")
    raw_text = raw_bytes.decode("utf-8", errors="replace").lstrip("\ufeff \t\r\n")
    try:
        parsed = json.loads(raw_text)
        if not expect_list or isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    decoder = json.JSONDecoder()
    delimiters = [idx for idx, ch in enumerate(raw_text) if ch in ("[", "{")]
    fallback_obj: Any = None
    for idx in delimiters:
        try:
            candidate, _ = decoder.raw_decode(raw_text, idx)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict) and fallback_obj is None:
            fallback_obj = candidate
            if not expect_list:
                return fallback_obj
    if fallback_obj is not None and not expect_list:
        return fallback_obj
    raise ValueError("Response did not contain a valid JSON payload")


def _request_once(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str],
    auth: tuple[str, str] | None,
    app_env: str,
    secrets: tuple[str, ...],
) -> httpx.Response:
    current_url = url
    current_params: dict[str, Any] | None = params
    for _ in range(_MAX_REDIRECTS + 1):
        response = client.get(current_url, params=current_params, headers=headers, auth=auth)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            redirect_target = _safe_redirect_url(str(response.url), location, app_env=app_env)
            if redirect_target is None:
                logger.warning(
                    "WordPress blocked/unsafe redirect status=%s url=%s location=%s",
                    response.status_code,
                    _sanitize_url_for_log(str(response.url)),
                    _sanitize_log_snippet(location, secrets=secrets, limit=180),
                )
                return response
            current_url = redirect_target
            current_params = None
            continue
        return response
    return response


def _log_wp_failure(
    *,
    path: str,
    auth_mode: str,
    response: httpx.Response | None,
    reason: str,
    secrets: tuple[str, ...],
) -> None:
    if response is None:
        logger.warning("WordPress request failed path=%s auth_mode=%s reason=%s", path, auth_mode, reason)
        return
    raw_snippet = _sanitize_log_snippet(response.text or "", secrets=secrets, limit=300)
    logger.warning(
        "WordPress request failed path=%s auth_mode=%s status=%s content_type=%s reason=%s body_prefix=%r",
        path,
        auth_mode,
        response.status_code,
        response.headers.get("content-type", ""),
        reason,
        raw_snippet,
    )


def _fetch_all(path: str, *, authenticated: bool, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    app_env = str(getattr(settings, "app_env", "production")).lower()
    ck = str(getattr(settings, "wordpress_consumer_key", "") or "")
    cs = str(getattr(settings, "wordpress_consumer_secret", "") or "")
    wp_user = str(getattr(settings, "wordpress_username", "") or "")
    wp_app_pw = str(getattr(settings, "wordpress_application_password", "") or "")
    secrets = tuple(s for s in (ck, cs, wp_app_pw) if s)

    basic_auth: tuple[str, str] | None = None
    query_auth_creds: tuple[str, str] | None = None
    if authenticated:
        if ck and cs:
            basic_auth = (ck, cs)
            query_auth_creds = (ck, cs)
        elif wp_user and wp_app_pw:
            basic_auth = (wp_user, wp_app_pw)
        else:
            raise HTTPException(status_code=503, detail="Set WORDPRESS_CONSUMER_KEY and WORDPRESS_CONSUMER_SECRET in the API environment")

    url = _configured_rest_url(path)
    default_page_size = max(1, min(int(getattr(settings, "wordpress_per_page", 20) or 20), 100))

    def run_pagination(page_size: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        auth_mode = "basic_header" if basic_auth else "public"
        with httpx.Client(timeout=25, follow_redirects=False) as client:
            for page in range(1, 501):
                params: dict[str, Any] = {"per_page": page_size, "page": page, **(extra_params or {})}
                active_auth = basic_auth if auth_mode == "basic_header" else None
                if auth_mode == "query_params" and query_auth_creds:
                    params["consumer_key"] = query_auth_creds[0]
                    params["consumer_secret"] = query_auth_creds[1]

                try:
                    response = _request_once(
                        client,
                        url,
                        params=params,
                        headers=_REQUEST_HEADERS,
                        auth=active_auth,
                        app_env=app_env,
                        secrets=secrets,
                    )
                except httpx.TimeoutException as error:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=None, reason="timeout", secrets=secrets)
                    raise HTTPException(status_code=504, detail=f"WordPress timed out on {path} (page {page})") from error
                except httpx.HTTPError as error:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=None, reason=type(error).__name__, secrets=secrets)
                    raise HTTPException(status_code=502, detail=f"Could not connect to WordPress REST endpoint {path}") from error

                if response.status_code in (401, 403) and authenticated and auth_mode == "basic_header" and query_auth_creds:
                    _log_wp_failure(
                        path=path,
                        auth_mode=auth_mode,
                        response=response,
                        reason="basic_auth_rejected_retrying_query_auth",
                        secrets=secrets,
                    )
                    auth_mode = "query_params"
                    retry_params = {**params, "consumer_key": query_auth_creds[0], "consumer_secret": query_auth_creds[1]}
                    try:
                        response = _request_once(
                            client,
                            url,
                            params=retry_params,
                            headers=_REQUEST_HEADERS,
                            auth=None,
                            app_env=app_env,
                            secrets=secrets,
                        )
                    except httpx.TimeoutException as error:
                        raise HTTPException(status_code=504, detail=f"WordPress timed out on {path} query auth retry") from error
                    except httpx.HTTPError as error:
                        raise HTTPException(status_code=502, detail=f"Could not connect to WordPress REST endpoint {path}") from error

                if response.status_code in (401, 403):
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="auth_rejected", secrets=secrets)
                    raise HTTPException(status_code=502, detail=f"WordPress rejected the REST credentials or access for {path} (HTTP {response.status_code})")
                if response.status_code == 404:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="not_found", secrets=secrets)
                    raise HTTPException(status_code=502, detail=f"WordPress REST route not found: {path}")
                if response.status_code >= 500:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="upstream_5xx", secrets=secrets)
                    raise HTTPException(
                        status_code=502,
                        detail=f"WordPress returned HTTP {response.status_code} ({response.headers.get('content-type', 'unknown')}) from {path}",
                    )
                try:
                    response.raise_for_status()
                    payload = _safe_json(response, expect_list=True)
                except (httpx.HTTPError, ValueError) as error:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason=f"invalid_json:{error}", secrets=secrets)
                    raise HTTPException(status_code=502, detail=f"WordPress returned an invalid response from {path}") from error

                if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="unexpected_json_shape", secrets=secrets)
                    raise HTTPException(status_code=502, detail=f"WordPress returned an unexpected response from {path}")

                rows.extend(payload)
                try:
                    total_pages = int(response.headers.get("X-WP-TotalPages", "0"))
                except ValueError:
                    total_pages = 0
                if total_pages and page >= total_pages:
                    return rows
                if not payload or len(payload) < page_size:
                    return rows
        raise HTTPException(status_code=413, detail="WordPress sync exceeded 10,000 records; narrow the product scope before syncing")

    try:
        return run_pagination(default_page_size)
    except HTTPException as first_error:
        if first_error.status_code in (502, 504) and default_page_size > 10:
            smaller_size = 25 if default_page_size > 25 else 10
            logger.warning(
                "Retrying WordPress fetch path=%s with reduced per_page=%s after %s",
                path,
                smaller_size,
                first_error.detail,
            )
            try:
                return run_pagination(smaller_size)
            except HTTPException as second_error:
                if second_error.status_code in (502, 504) and smaller_size > 10:
                    logger.warning("Retrying WordPress fetch path=%s with per_page=10", path)
                    return run_pagination(10)
                raise
        raise


_ORIGINAL_FETCH_ALL = _fetch_all


def _fetch_pdf_media_resilient(path: str) -> tuple[list[dict[str, Any]], str]:
    """Fetch PDF attachments from wp/v2/media keeping already-fetched pages if a later page fails."""
    if not path or not path.strip():
        return [], "skipped_unconfigured"
    if _fetch_all is not _ORIGINAL_FETCH_ALL:
        rows = _optional_fetch_all(path, extra_params={"mime_type": "application/pdf"})
        return rows, f"mocked:{len(rows)}"

    settings = get_settings()
    app_env = str(getattr(settings, "app_env", "production")).lower()
    ck = str(getattr(settings, "wordpress_consumer_key", "") or "")
    cs = str(getattr(settings, "wordpress_consumer_secret", "") or "")
    wp_user = str(getattr(settings, "wordpress_username", "") or "")
    wp_app_pw = str(getattr(settings, "wordpress_application_password", "") or "")
    secrets = tuple(s for s in (ck, cs, wp_app_pw) if s)
    url = _configured_rest_url(path)

    rows: list[dict[str, Any]] = []
    auth_mode = "public"
    page_size = 100
    status_note = "ok"

    with httpx.Client(timeout=25, follow_redirects=False) as client:
        page = 1
        while page <= 15:
            params: dict[str, Any] = {"mime_type": "application/pdf", "per_page": page_size, "page": page}
            auth = None
            if auth_mode == "query_params" and ck and cs:
                params["consumer_key"] = ck
                params["consumer_secret"] = cs
            elif auth_mode == "basic_header":
                if wp_user and wp_app_pw:
                    auth = (wp_user, wp_app_pw)
                elif ck and cs:
                    auth = (ck, cs)

            try:
                response = _request_once(
                    client, url, params=params, headers=_REQUEST_HEADERS, auth=auth, app_env=app_env, secrets=secrets
                )
            except (httpx.TimeoutException, httpx.HTTPError) as error:
                _log_wp_failure(path=path, auth_mode=auth_mode, response=None, reason=type(error).__name__, secrets=secrets)
                if page == 1 and page_size > 25:
                    page_size = 25
                    continue
                status_note = f"partial_{type(error).__name__}:{len(rows)}"
                break

            if page == 1 and response.status_code in (401, 403):
                if auth_mode == "public" and ((wp_user and wp_app_pw) or (ck and cs)):
                    auth_mode = "query_params" if (ck and cs) else "basic_header"
                    continue
                if auth_mode == "query_params" and ck and cs:
                    auth_mode = "basic_header"
                    continue
                _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="media_auth_rejected", secrets=secrets)
                return [], f"http_{response.status_code}"

            if response.status_code in (400, 404):
                if response.status_code == 400 and page == 1 and page_size > 25:
                    page_size = 25
                    continue
                # WordPress returns 400 rest_post_invalid_page_number past final page.
                status_note = f"ok_end_page_{page}:{len(rows)}" if rows else f"http_{response.status_code}"
                if not rows:
                    _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="media_client_error", secrets=secrets)
                break

            if response.status_code >= 500:
                _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason="media_5xx", secrets=secrets)
                if page == 1 and page_size > 25:
                    page_size = 25
                    continue
                status_note = f"partial_http_{response.status_code}:{len(rows)}"
                break

            try:
                payload = _safe_json(response, expect_list=True)
            except ValueError as error:
                _log_wp_failure(path=path, auth_mode=auth_mode, response=response, reason=f"media_bad_json:{error}", secrets=secrets)
                status_note = f"partial_bad_json:{len(rows)}"
                break

            if not isinstance(payload, list):
                break
            batch = [item for item in payload if isinstance(item, dict)]
            if not batch:
                if page == 1 and auth_mode == "public" and ((wp_user and wp_app_pw) or (ck and cs)):
                    auth_mode = "query_params" if (ck and cs) else "basic_header"
                    continue
                break
            rows.extend(batch)
            try:
                total_pages = int(response.headers.get("X-WP-TotalPages", "0"))
            except ValueError:
                total_pages = 0
            if (total_pages and page >= total_pages) or len(batch) < page_size:
                break
            page += 1

    if status_note == "ok":
        status_note = f"ok:{len(rows)}"
    return rows, status_note


def _fetch(limit: int, page: int = 1) -> tuple[list[dict[str, Any]], Any]:
    settings = get_settings()
    app_env = str(getattr(settings, "app_env", "production")).lower()
    ck = str(getattr(settings, "wordpress_consumer_key", "") or "")
    cs = str(getattr(settings, "wordpress_consumer_secret", "") or "")
    wp_user = str(getattr(settings, "wordpress_username", "") or "")
    wp_app_pw = str(getattr(settings, "wordpress_application_password", "") or "")
    credentials_ready = bool((ck and cs) or (wp_user and wp_app_pw))
    using_store_api = not credentials_ready
    path = settings.wordpress_store_products_path if using_store_api else settings.wordpress_products_path
    url = _configured_rest_url(path)
    params: dict[str, Any] = {"per_page": min(limit, 25), "page": page}
    if not using_store_api:
        params["status"] = "publish"
    auth = (ck, cs) if (ck and cs) else (wp_user, wp_app_pw) if (wp_user and wp_app_pw) else None
    secrets = tuple(s for s in (ck, cs, wp_app_pw) if s)

    with httpx.Client(timeout=20, follow_redirects=False) as client:
        try:
            response = _request_once(client, url, params=params, headers=_REQUEST_HEADERS, auth=auth, app_env=app_env, secrets=secrets)
            if response.status_code in (401, 403) and ck and cs:
                response = _request_once(
                    client,
                    url,
                    params={**params, "consumer_key": ck, "consumer_secret": cs},
                    headers=_REQUEST_HEADERS,
                    auth=None,
                    app_env=app_env,
                    secrets=secrets,
                )
            if response.status_code in (401, 403):
                _log_wp_failure(path=path, auth_mode="preview", response=response, reason="auth_rejected", secrets=secrets)
                raise HTTPException(status_code=502, detail="WordPress rejected the configured REST API credentials or endpoint access")
            if response.status_code == 404:
                raise HTTPException(status_code=502, detail="WordPress product route was not found; check the configured products or Store API path")
            response.raise_for_status()
            payload = _safe_json(response, expect_list=True)
            if not isinstance(payload, list):
                _log_wp_failure(path=path, auth_mode="preview", response=response, reason="unexpected_json_shape", secrets=secrets)
                raise HTTPException(status_code=502, detail="WordPress returned an unexpected product response")
            return [item for item in payload if isinstance(item, dict)], settings
        except HTTPException:
            raise
        except httpx.TimeoutException as error:
            _log_wp_failure(path=path, auth_mode="preview", response=None, reason="timeout", secrets=secrets)
            raise HTTPException(status_code=504, detail="WordPress did not respond before the connection timed out") from error
        except (httpx.HTTPError, ValueError) as error:
            _log_wp_failure(path=path, auth_mode="preview", response=None, reason=str(error), secrets=secrets)
            raise HTTPException(status_code=502, detail="Could not fetch products from WordPress") from error


def _minor_units(value: Any, digits: int, *, already_minor: bool = False) -> int | None:
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            return None
        if already_minor and amount == amount.to_integral_value():
            return int(amount)
        factor = Decimal(10) ** max(0, min(digits, 4))
        return int((amount * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_currency(value: Any) -> str:
    value = str(value or "INR").upper()
    return value if len(value) == 3 and value.isalpha() else "INR"


def _https_url(value: Any, *, site_origin: str = "") -> str | None:
    """Normalize HTTP/HTTPS or relative site paths to canonical HTTPS URLs (like toHttpsUrl)."""
    if not isinstance(value, str):
        return None
    candidate = unescape(value).replace("\\/", "/").strip().strip("\"'")
    if not candidate:
        return None
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"
    elif candidate.startswith("/") and site_origin:
        origin_https = f"https://{site_origin[7:]}" if site_origin.lower().startswith("http://") else site_origin
        candidate = urljoin(f"{origin_https.rstrip('/')}/", candidate.lstrip("/"))
    elif candidate.lower().startswith("wp-content/") and site_origin:
        origin_https = f"https://{site_origin[7:]}" if site_origin.lower().startswith("http://") else site_origin
        candidate = urljoin(f"{origin_https.rstrip('/')}/", candidate)
    elif candidate.lower().startswith("http://"):
        parsed = urlparse(candidate)
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            candidate = f"https://{candidate[7:]}"
    if not candidate.lower().startswith("https://"):
        return None
    candidate = f"https://{candidate[8:]}"
    return candidate[:1000]


def _extract_pdf_urls_from_value(
    value: Any,
    fallback_title: str,
    found: dict[str, str],
    *,
    site_origin: str = "",
    media_by_id: dict[str, dict[str, Any]] | None = None,
    allow_direct_non_pdf_url: bool = False,
    depth: int = 0,
) -> None:
    if depth > 6 or value is None:
        return
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        media_item = (media_by_id or {}).get(str(value).strip())
        if media_item and str(media_item.get("mime_type") or "") == "application/pdf":
            url = _https_url(media_item.get("source_url"), site_origin=site_origin)
            if url and url not in found:
                title = _plain(_field(media_item, "title.rendered", fallback_title), 180)
                found[url] = title or fallback_title or "Product datasheet"
        return
    if isinstance(value, list):
        for nested in value[:24]:
            _extract_pdf_urls_from_value(
                nested,
                fallback_title,
                found,
                site_origin=site_origin,
                media_by_id=media_by_id,
                allow_direct_non_pdf_url=allow_direct_non_pdf_url,
                depth=depth + 1,
            )
        return
    if isinstance(value, dict):
        title = _plain(value.get("title") or value.get("name") or value.get("label") or fallback_title, 180)
        for key in ("url", "file", "source_url", "guid", "link", "href"):
            raw_url = value.get(key)
            if isinstance(raw_url, str):
                _extract_pdf_urls_from_value(
                    raw_url,
                    title,
                    found,
                    site_origin=site_origin,
                    media_by_id=media_by_id,
                    allow_direct_non_pdf_url=allow_direct_non_pdf_url,
                    depth=depth + 1,
                )
        for key in ("id", "attachment_id", "ID"):
            if key in value and isinstance(value[key], (int, str)):
                _extract_pdf_urls_from_value(
                    value[key],
                    title,
                    found,
                    site_origin=site_origin,
                    media_by_id=media_by_id,
                    allow_direct_non_pdf_url=allow_direct_non_pdf_url,
                    depth=depth + 1,
                )
        for key, nested in value.items():
            if key not in {"url", "file", "source_url", "guid", "link", "href", "title", "name", "label", "id", "attachment_id", "ID"} and isinstance(nested, (dict, list)):
                _extract_pdf_urls_from_value(
                    nested,
                    title,
                    found,
                    site_origin=site_origin,
                    media_by_id=media_by_id,
                    allow_direct_non_pdf_url=allow_direct_non_pdf_url,
                    depth=depth + 1,
                )
        return
    if not isinstance(value, str):
        return
    text = unescape(value.strip()).replace("\\/", "/")
    direct = _https_url(text, site_origin=site_origin)
    urls: list[str] = []
    if direct and (allow_direct_non_pdf_url or direct.lower().split("?", 1)[0].endswith(".pdf")):
        urls.append(direct)
    urls.extend(re.findall(r"https?://[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?", text, flags=re.IGNORECASE))
    for rel in re.findall(r"(?:href|src|url)\s*[:=]\s*[\"']((?:/|wp-content/)[^\"']+?\.pdf(?:\?[^\"']*)?)[\"']", text, flags=re.IGNORECASE):
        resolved = _https_url(rel, site_origin=site_origin)
        if resolved:
            urls.append(resolved)
    for raw_url in urls:
        url = _https_url(raw_url.rstrip(".,);]"), site_origin=site_origin)
        if url and url not in found:
            found[url] = fallback_title or "Product datasheet"


def _documents(
    product: dict[str, Any],
    media: list[dict[str, Any]],
    field_path: str = "",
    *,
    site_origin: str = "",
    wp_record: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    source_id = str(product.get("id", ""))
    found: dict[str, str] = {}
    media_by_id = {str(item.get("id")): item for item in media if item.get("id") is not None}
    candidates: list[tuple[Any, str, bool]] = []

    downloads = product.get("downloads")
    if isinstance(downloads, list):
        candidates.extend((item, "Product brochure", True) for item in downloads)
    if field_path.strip():
        mapped = _field(product, field_path.strip())
        candidates.extend((item, "Product datasheet", False) for item in (mapped if isinstance(mapped, list) else [mapped]))

    for source_dict in (product, wp_record or {}):
        if isinstance(source_dict.get("acf"), dict):
            for key, val in source_dict["acf"].items():
                is_doc_key = bool(re.search(r"catalog(?:ue)?|pdf|datasheet|brochure|download|file|manual|spec", str(key), re.IGNORECASE))
                if is_doc_key or (isinstance(val, str) and ".pdf" in val.lower()):
                    candidates.append((val, _plain(str(key).replace("_", " "), 180) or "Product datasheet", False))
        for field in source_dict.get("meta_data", []) if isinstance(source_dict.get("meta_data"), list) else []:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key") or field.get("name") or "")
            raw_val = field.get("value")
            if re.search(r"catalog(?:ue)?|pdf|datasheet|brochure|download", key, re.IGNORECASE):
                candidates.append((raw_val, _plain(key.replace("_", " "), 180) or "Product datasheet", False))
            elif key.lower() == "_elementor_data" and isinstance(raw_val, str) and ".pdf" in raw_val.lower():
                candidates.append((raw_val, "Product brochure", False))

    for candidate, title, allow_non_pdf in candidates:
        _extract_pdf_urls_from_value(
            candidate,
            title,
            found,
            site_origin=site_origin,
            media_by_id=media_by_id,
            allow_direct_non_pdf_url=allow_non_pdf,
        )

    for source_dict in (product, wp_record or {}):
        for field_name in ("description", "short_description"):
            val = source_dict.get(field_name)
            if isinstance(val, str):
                _extract_pdf_urls_from_value(val, "Product datasheet", found, site_origin=site_origin, media_by_id=media_by_id)
        content_rendered = _field(source_dict, "content.rendered")
        if isinstance(content_rendered, str):
            _extract_pdf_urls_from_value(content_rendered, "Product datasheet", found, site_origin=site_origin, media_by_id=media_by_id)

    for item in media:
        attachment_parent = item.get("post") if item.get("post") is not None else item.get("parent")
        if not source_id or str(attachment_parent) != source_id:
            continue
        mime = str(item.get("mime_type") or "")
        url = _https_url(item.get("source_url"), site_origin=site_origin)
        if (mime == "application/pdf" or (url and url.lower().split("?", 1)[0].endswith(".pdf"))) and url and url not in found:
            title = _plain(_field(item, "title.rendered", "Product document"), 180)
            found[url] = title or "Product document"
    return [{"title": title, "url": url} for url, title in list(found.items())[:24]]


def _extract_html_pdf_documents(html_text: str, *, site_origin: str, default_title: str = "Product brochure") -> list[dict[str, str]]:
    """Extract brochure PDF links from main page HTML while excluding global header/nav/footer menus."""
    if not html_text:
        return []
    scoped = _HTML_STRIP_SECTIONS_RE.sub(" ", html_text)
    main_match = re.search(r"<main\b[^>]*>(.*?)</main>", scoped, flags=re.IGNORECASE | re.DOTALL)
    if main_match:
        scoped = main_match.group(1)

    found: dict[str, str] = {}
    for pre_attrs, href, post_attrs, inner in _HTML_ANCHOR_RE.findall(scoped):
        url = _https_url(href, site_origin=site_origin)
        if not url:
            continue
        if not url.lower().split("?", 1)[0].endswith(".pdf"):
            continue
        label = _plain(inner, 160)
        attrs_blob = f"{pre_attrs} {post_attrs}"
        if label and _DOWNLOAD_HINT_RE.search(label):
            title = default_title if re.fullmatch(r"download(?:\s+(?:now|pdf|brochure|catalogue|catalog))?", label, re.I) else label
        elif _DOWNLOAD_HINT_RE.search(attrs_blob):
            title = label or default_title
        else:
            title = label or default_title
        if url not in found:
            found[url] = title[:180]

    # Secondary pass inside stripped content for JSON-escaped URLs in Elementor / JS data attributes.
    unescaped = unescape(scoped).replace("\\/", "/")
    for raw_url in re.findall(r"https?://[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?", unescaped, flags=re.IGNORECASE):
        url = _https_url(raw_url.rstrip(".,);]"), site_origin=site_origin)
        if url and url not in found:
            found[url] = default_title
    return [{"title": title, "url": url} for url, title in list(found.items())[:12]]


def _fetch_html_page(url: str, *, site_origin: str, app_env: str) -> str:
    try:
        with httpx.Client(timeout=8, follow_redirects=False) as client:
            resp = _request_once(
                client, url, params=None, headers=_HTML_HEADERS, auth=None, app_env=app_env, secrets=()
            )
            if 200 <= resp.status_code < 300 and "html" in (resp.headers.get("content-type") or "html").lower():
                return resp.text or ""
    except httpx.HTTPError:
        return ""
    return ""


def _extract_category_catalogue_pdf(
    category_source: dict[str, Any],
    wp_cat_record: dict[str, Any] | None,
    media: list[dict[str, Any]],
    *,
    site_origin: str = "",
) -> tuple[str, str] | None:
    found: dict[str, str] = {}
    media_by_id = {str(item.get("id")): item for item in media if item.get("id") is not None}
    wp_id = str(category_source.get("id", ""))
    cat_name = _plain(category_source.get("name"), 140) or "Category"

    for record in (category_source, wp_cat_record or {}):
        if not isinstance(record, dict):
            continue
        if isinstance(record.get("acf"), dict):
            for key, val in record["acf"].items():
                if re.search(r"catalog(?:ue)?|pdf|datasheet|brochure|download|file", str(key), re.IGNORECASE) or (
                    isinstance(val, str) and ".pdf" in val.lower()
                ):
                    _extract_pdf_urls_from_value(
                        val, f"{cat_name} Catalogue PDF", found, site_origin=site_origin, media_by_id=media_by_id
                    )
        for field in record.get("meta_data", []) if isinstance(record.get("meta_data"), list) else []:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key") or field.get("name") or "")
            raw_val = field.get("value")
            if re.search(r"catalog(?:ue)?|pdf|datasheet|brochure|download", key, re.IGNORECASE) or (
                isinstance(raw_val, str) and ".pdf" in raw_val.lower()
            ):
                _extract_pdf_urls_from_value(
                    raw_val, f"{cat_name} Catalogue PDF", found, site_origin=site_origin, media_by_id=media_by_id
                )
        if isinstance(record.get("description"), str):
            _extract_pdf_urls_from_value(
                record["description"], f"{cat_name} Catalogue PDF", found, site_origin=site_origin, media_by_id=media_by_id
            )

    for item in media:
        attachment_parent = item.get("post") if item.get("post") is not None else item.get("parent")
        if wp_id and str(attachment_parent) == wp_id:
            mime = str(item.get("mime_type") or "")
            url = _https_url(item.get("source_url"), site_origin=site_origin)
            if (mime == "application/pdf" or (url and url.lower().split("?", 1)[0].endswith(".pdf"))) and url and url not in found:
                title = _plain(_field(item, "title.rendered", f"{cat_name} Catalogue PDF"), 180)
                found[url] = title or f"{cat_name} Catalogue PDF"

    if not found:
        return None
    url, title = next(iter(found.items()))
    return url, title


def _upsert_category_catalogue_mapping(
    session: Session,
    *,
    category: ProductCategory,
    wp_id: str | None,
    pdf_url: str,
    title: str,
    source: str,
) -> None:
    existing = session.scalar(
        select(ProductCategoryCatalogue).where(
            (ProductCategoryCatalogue.category_id == category.id)
            | (ProductCategoryCatalogue.category_key == category.slug)
        )
    )
    if existing is None:
        session.add(
            ProductCategoryCatalogue(
                category_key=category.slug,
                category_id=category.id,
                wordpress_category_id=wp_id,
                title=title[:180],
                catalog_pdf_url=pdf_url[:1000],
                source=source,
            )
        )
    else:
        if existing.source == "cms" and source == "wordpress":
            return
        existing.category_key = category.slug
        existing.category_id = category.id
        existing.wordpress_category_id = wp_id or existing.wordpress_category_id
        existing.title = title[:180]
        existing.catalog_pdf_url = pdf_url[:1000]
        existing.source = source


def _optional_fetch_all(path: str, *, extra_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not path or not path.strip():
        return []
    try:
        return _fetch_all(path, authenticated=False, extra_params=extra_params)
    except HTTPException as error:
        logger.warning("Optional WordPress endpoint skipped path=%s detail=%s", path, error.detail)
        return []


_BROAD_UMBRELLA_CATEGORY_SLUGS = frozenset({
    "uncategorized",
    "power-products",
    "solar-products",
    "renewable-energy-solutions",
    "balance-of-system",
})


def _pick_default_primary_category(
    selected_categories: list[ProductCategory],
    batch_freq_by_cat_id: dict[UUID, int],
) -> ProductCategory:
    """Prefer specific published collections over broad parent or uncategorized buckets."""
    return min(
        enumerate(selected_categories),
        key=lambda pair: (
            0 if pair[1].is_published else 1,
            1 if pair[1].slug in _BROAD_UMBRELLA_CATEGORY_SLUGS else 0,
            batch_freq_by_cat_id.get(pair[1].id, 10**6),
            pair[0],
        ),
    )[1]


def _slug_for_product(session: Session, slug: str, source_id: str, existing: Product | None) -> str:
    base = slug or f"wordpress-product-{source_id}"
    candidate = base[:180]
    conflict = session.scalar(select(Product).where(Product.slug == candidate))
    if conflict is None or (existing is not None and conflict.id == existing.id):
        return candidate
    suffix = f"-wp-{source_id}"
    return f"{base[:180-len(suffix)]}{suffix}"


@router.get("/status")
def wordpress_status(_admin: AdminIdentity = Depends(require_admin_roles(*ROLES))) -> dict[str, Any]:
    settings = get_settings()
    credentials_ready = bool(settings.wordpress_consumer_key and settings.wordpress_consumer_secret)
    rest_ready = bool(settings.wordpress_api_base_url and credentials_ready and settings.wordpress_products_path and settings.wordpress_categories_path)
    configured = bool(settings.wordpress_api_base_url and (rest_ready or settings.wordpress_store_products_path))
    message = (
        "Ready to pull the WooCommerce catalogue using authenticated REST"
        if rest_ready
        else "Ready to pull public WooCommerce catalogue data using the Store API"
        if configured
        else "Set the WordPress URL and WooCommerce REST or Store API routes"
    )
    return {
        "configured": configured,
        "authenticated": credentials_ready,
        "documents_configured": bool(settings.wordpress_documents_path or getattr(settings, "wordpress_source_documents_field", "")),
        "site": settings.wordpress_api_base_url or None,
        "products_path": settings.wordpress_products_path or None,
        "categories_path": settings.wordpress_categories_path or None,
        "store_api_path": settings.wordpress_store_products_path or None,
        "message": message,
    }


@router.post("/sync")
def sync_woocommerce_catalogue(
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("content_editor", "admin", "super_admin")),
) -> dict[str, Any]:
    settings = get_settings()
    app_env = str(getattr(settings, "app_env", "production")).lower()
    raw_base = getattr(settings, "wordpress_api_base_url", "")
    if not raw_base:
        raise HTTPException(status_code=503, detail="Configure WORDPRESS_API_BASE_URL in the API environment")
    normalized_base = _normalize_wp_base_url(raw_base, app_env=app_env)
    site_origin = _site_origin(normalized_base)

    credentials_ready = bool(settings.wordpress_consumer_key and settings.wordpress_consumer_secret)
    rest_ready = bool(credentials_ready and settings.wordpress_products_path and settings.wordpress_categories_path)
    store_path = getattr(settings, "wordpress_store_products_path", "")
    sync_source_mode = "wc/v3/products"
    fallback_used: str | None = None

    if rest_ready:
        try:
            source_products = _fetch_all(settings.wordpress_products_path, authenticated=True, extra_params={"status": "publish"})
            source_categories = _fetch_all(settings.wordpress_categories_path, authenticated=True, extra_params={"hide_empty": "false"})
        except HTTPException as primary_error:
            if store_path and primary_error.status_code in (502, 504):
                logger.warning("Primary WooCommerce REST failed (%s); falling back to Store API %s", primary_error.detail, store_path)
                source_products = _fetch_all(store_path, authenticated=False)
                source_categories = []
                sync_source_mode = store_path
                fallback_used = store_path
            else:
                raise
    elif store_path:
        source_products = _fetch_all(store_path, authenticated=False)
        source_categories = []
        sync_source_mode = store_path
    else:
        raise HTTPException(status_code=503, detail="Configure WooCommerce REST credentials or the public Store API route")

    if not source_products:
        raise HTTPException(status_code=409, detail="WooCommerce returned no products; sync made no changes")

    store_products = source_products if (fallback_used or not rest_ready) else []
    store_by_id = {str(row.get("id")): row for row in store_products if row.get("id") is not None}

    docs_path = getattr(settings, "wordpress_documents_path", "")
    source_media, media_fetch_status = _fetch_pdf_media_resilient(docs_path)
    wp_products_by_id: dict[str, dict[str, Any]] = {}
    wp_categories_by_id: dict[str, dict[str, Any]] = {}

    if not source_categories:
        discovered: dict[str, dict[str, Any]] = {}
        for product in source_products:
            for category in product.get("categories", []) if isinstance(product.get("categories"), list) else []:
                if isinstance(category, dict) and category.get("id") is not None and category.get("name"):
                    discovered.setdefault(str(category["id"]), category)
        source_categories = list(discovered.values())

    wp_batch_freq_by_wp_id: dict[str, int] = {}
    for src in source_products:
        for cat_entry in src.get("categories", []) if isinstance(src.get("categories"), list) else []:
            if isinstance(cat_entry, dict) and cat_entry.get("id") is not None:
                cid_str = str(cat_entry["id"])
                wp_batch_freq_by_wp_id[cid_str] = wp_batch_freq_by_wp_id.get(cid_str, 0) + 1

    categories_by_wp_id: dict[str, ProductCategory] = {}
    category_rows = 0
    category_catalogues_synced = 0
    cms_preserved_categories = 0
    missing_cat_html_targets: list[tuple[ProductCategory, str, str]] = []

    for item in source_categories:
        wp_id = str(item.get("id", ""))
        name = _plain(item.get("name"), 180)
        if not wp_id or not name:
            continue
        slug = str(item.get("slug") or f"category-{wp_id}")[:120]
        raw_wp_count = item.get("count")
        effective_count = wp_batch_freq_by_wp_id.get(wp_id, 0) or (
            int(raw_wp_count) if isinstance(raw_wp_count, int) else 0
        )
        should_publish_default = slug != "uncategorized" and effective_count > 0
        category = session.scalar(select(ProductCategory).where(ProductCategory.wordpress_source_id == wp_id))
        if category is None:
            slug_match = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if slug_match is not None and slug_match.wordpress_source_id in (None, wp_id):
                category = slug_match
        image = _image_url(item.get("image"), site_origin=site_origin)
        description = _plain(item.get("description"), 3000) or None
        if category is None:
            collision = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if collision is not None:
                suffix = f"-wp-{wp_id}"
                slug = f"{slug[:120-len(suffix)]}{suffix}"
            category = ProductCategory(
                slug=slug, name=name, description=description,
                sort_order=int(item.get("menu_order") or 0),
                image_url=image, wordpress_source_id=wp_id, is_published=should_publish_default,
            )
            session.add(category)
        elif category.cms_locked:
            category.wordpress_source_id = wp_id
            category.image_url = category.image_url or image
            cms_preserved_categories += 1
        else:
            slug_conflict = session.scalar(select(ProductCategory).where(ProductCategory.slug == slug))
            if slug_conflict is not None and slug_conflict.id != category.id:
                suffix = f"-wp-{wp_id}"
                slug = f"{slug[:120-len(suffix)]}{suffix}"
            category.slug = slug
            category.name = name
            category.description = description
            category.sort_order = int(item.get("menu_order") or 0)
            category.image_url = image or category.image_url
            category.wordpress_source_id = wp_id
            category.is_published = should_publish_default
        session.flush()
        categories_by_wp_id[wp_id] = category
        category_rows += 1

        cat_pdf = _extract_category_catalogue_pdf(item, wp_categories_by_id.get(wp_id), source_media, site_origin=site_origin)
        if cat_pdf is not None:
            cat_pdf_url, cat_pdf_title = cat_pdf
            _upsert_category_catalogue_mapping(
                session, category=category, wp_id=wp_id, pdf_url=cat_pdf_url, title=cat_pdf_title, source="wordpress"
            )
            category_catalogues_synced += 1
        elif site_origin:
            cat_link = _https_url(item.get("link") or _field(wp_categories_by_id.get(wp_id, {}), "link"), site_origin=site_origin)
            if not cat_link:
                cat_link = f"{site_origin}/product-category/{slug}/"
            missing_cat_html_targets.append((category, wp_id, cat_link))

    batch_freq_by_cat_id = {
        cat.id: wp_batch_freq_by_wp_id.get(wp_cid, 10**6)
        for wp_cid, cat in categories_by_wp_id.items()
    }
    created = updated = skipped = 0
    matched_by_rest = matched_by_media = matched_by_html = 0
    cms_preserved_category_products = 0
    cms_preserved_pdf_products = 0
    source_wp_ids = {str(row.get("id")) for row in source_products if row.get("id") is not None}
    doc_field_path = getattr(settings, "wordpress_source_documents_field", "")
    synced_products: list[Product] = []
    products_needing_html: list[tuple[Product, str]] = []

    for source in source_products:
        wp_id = str(source.get("id", ""))
        if not wp_id:
            skipped += 1
            continue
        wp_categories_list = source.get("categories") if isinstance(source.get("categories"), list) else []
        selected_categories = list(dict.fromkeys(
            categories_by_wp_id[str(row.get("id"))]
            for row in wp_categories_list
            if isinstance(row, dict) and categories_by_wp_id.get(str(row.get("id"))) is not None
        ))

        product = session.scalar(select(Product).where(Product.wordpress_source_id == wp_id))

        if not selected_categories:
            if product is not None and product.categories:
                selected_categories = list(product.categories)
            else:
                fallback_category = session.scalar(select(ProductCategory).where(ProductCategory.slug == "uncategorized"))
                if fallback_category is None:
                    fallback_category = ProductCategory(
                        slug="uncategorized",
                        name="Uncategorized",
                        description="Products without a WooCommerce category.",
                        is_published=False,
                    )
                    session.add(fallback_category)
                    session.flush()
                selected_categories = [fallback_category]
        selected_category = _pick_default_primary_category(selected_categories, batch_freq_by_cat_id)

        store = store_by_id.get(wp_id, {})
        title = _plain(_field(source, settings.wordpress_source_title_field, source.get("name", "")), 220)
        slug = str(_field(source, settings.wordpress_source_slug_field, source.get("slug", "")))[:180]
        if len(title) < 2:
            skipped += 1
            continue
        permalink = _https_url(source.get("permalink"), site_origin=site_origin)
        if not slug:
            slug = f"wordpress-product-{wp_id}"
        slug = _slug_for_product(session, slug, wp_id, product)
        summary = _plain(_field(source, settings.wordpress_source_summary_field, source.get("short_description", "")), 500) or None
        description = _plain(_field(source, settings.wordpress_source_description_field, source.get("description", "")), 12000, preserve_blocks=True) or None
        sku = _plain(_field(source, settings.wordpress_source_model_field, source.get("sku", "")), 120) or None
        images = source.get("images") if isinstance(source.get("images"), list) else store.get("images", [])
        image_url = _image_url(_field(source, settings.wordpress_source_image_field), site_origin=site_origin) or (
            _image_url(_field(store, "images.0"), site_origin=site_origin)
        )
        gallery = [_image_url(image, site_origin=site_origin) for image in images] if isinstance(images, list) else []
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

        rest_only_docs = _documents(
            source, [], doc_field_path, site_origin=site_origin, wp_record=wp_products_by_id.get(wp_id)
        )
        incoming_documents = (
            rest_only_docs
            if rest_only_docs
            else _documents(source, source_media, doc_field_path, site_origin=site_origin, wp_record=wp_products_by_id.get(wp_id))
        )
        if rest_only_docs:
            matched_by_rest += 1
        elif incoming_documents:
            matched_by_media += 1

        existing_documents = normalize_pdf_documents(product.documents) if product is not None else []
        documents = incoming_documents or existing_documents

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
        if product.category_override:
            cms_preserved_category_products += 1
        else:
            product.category_id = selected_category.id
            product.categories = selected_categories
        product.slug = slug
        product.name = title
        product.model_code = sku or product.model_code
        product.summary = summary or product.summary
        product.description = description or product.description
        product.applications = applications or list(product.applications or [])
        product.features = features or list(product.features or [])
        product.specifications = specifications or (dict(product.specifications) if isinstance(product.specifications, dict) else {})
        product.image_url = image_url or product.image_url
        product.gallery_images = gallery_images or list(product.gallery_images or [])
        if price_minor is not None:
            product.price_minor = price_minor
            product.currency_code = currency
            product.currency_minor_unit = minor_digits
        product.stock_status = stock_status if stock_status != "unknown" else (product.stock_status or "unknown")
        if quantity is not None:
            product.stock_quantity = quantity
        if product.documents_override:
            cms_preserved_pdf_products += 1
        else:
            product.documents = documents
        product.source_reference = permalink or product.source_reference
        product.wordpress_source_url = permalink or product.wordpress_source_url
        product.content_verified_at = datetime.now(timezone.utc)
        product.published_at = product.published_at or datetime.now(timezone.utc)
        product.is_published = True
        product.draft_data = None
        synced_products.append(product)

        if not product.documents_override and not documents and permalink:
            products_needing_html.append((product, permalink))

    # Optional scoped HTML fallback ONLY for items missing PDFs after REST & wp/v2/media.
    html_fallback_enabled = bool(getattr(settings, "wordpress_html_fallback_enabled", False))
    if html_fallback_enabled and site_origin and (products_needing_html or missing_cat_html_targets):
        deadline = time.monotonic() + 25.0
        with ThreadPoolExecutor(max_workers=10) as pool:
            cat_futures = {
                pool.submit(_fetch_html_page, cat_url, site_origin=site_origin, app_env=app_env): (cat_obj, wp_id)
                for cat_obj, wp_id, cat_url in missing_cat_html_targets
            }
            for fut in as_completed(cat_futures):
                if time.monotonic() > deadline:
                    break
                cat_obj, wp_id = cat_futures[fut]
                html_body = fut.result()
                html_docs = _extract_html_pdf_documents(
                    html_body, site_origin=site_origin, default_title=f"{cat_obj.name} Catalogue PDF"
                )
                if html_docs:
                    _upsert_category_catalogue_mapping(
                        session,
                        category=cat_obj,
                        wp_id=wp_id,
                        pdf_url=html_docs[0]["url"],
                        title=html_docs[0]["title"],
                        source="wordpress",
                    )
                    category_catalogues_synced += 1

            if time.monotonic() < deadline and products_needing_html:
                prod_futures = {
                    pool.submit(_fetch_html_page, purl, site_origin=site_origin, app_env=app_env): prod_obj
                    for prod_obj, purl in products_needing_html
                }
                for fut in as_completed(prod_futures):
                    if time.monotonic() > deadline:
                        break
                    prod_obj = prod_futures[fut]
                    html_body = fut.result()
                    html_docs = _extract_html_pdf_documents(html_body, site_origin=site_origin, default_title="Product brochure")
                    if html_docs and not prod_obj.documents_override:
                        prod_obj.documents = html_docs
                        matched_by_html += 1

    withdrawn = 0
    for product in session.scalars(select(Product).where(Product.wordpress_source_id.is_not(None), Product.is_published.is_(True))):
        if product.wordpress_source_id not in source_wp_ids:
            product.is_published = False
            withdrawn += 1

    session.flush()
    lookup = load_category_catalogue_lookup(session)
    resolved_with_pdfs = sum(1 for item in synced_products if resolve_product_documents_for_model(item, lookup)[1] is not None)

    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="wordpress.catalogue_synced",
        entity_type="catalogue_sync",
        entity_id="woocommerce",
        change_summary={
            "source_mode": sync_source_mode,
            "fallback_used": fallback_used,
            "media_fetch_status": media_fetch_status,
            "media_pdf_count": len(source_media),
            "matched_by_rest_fields": matched_by_rest,
            "matched_by_wp_media": matched_by_media,
            "matched_by_html": matched_by_html,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "withdrawn": withdrawn,
            "categories": category_rows,
            "cms_preserved_categories": cms_preserved_categories,
            "cms_preserved_category_products": cms_preserved_category_products,
            "cms_preserved_pdf_products": cms_preserved_pdf_products,
            "category_catalogues_synced": category_catalogues_synced,
            "documents_linked": resolved_with_pdfs,
            "source_products": len(source_products),
        },
    ))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        logger.exception("WooCommerce catalogue sync hit a database constraint")
        raise HTTPException(status_code=409, detail="WooCommerce sync could not be saved because of a catalogue conflict. Check for duplicate product or collection slugs.") from error
    except Exception as error:
        session.rollback()
        logger.exception("WooCommerce catalogue sync could not commit")
        raise HTTPException(status_code=500, detail="WooCommerce sync could not be saved. Check API runtime logs and try again.") from error

    return {
        "source": "woocommerce",
        "source_mode": sync_source_mode,
        "fallback_used": fallback_used,
        "media_fetch_status": media_fetch_status,
        "media_pdf_count": len(source_media),
        "matched_by_rest_fields": matched_by_rest,
        "matched_by_wp_media": matched_by_media,
        "matched_by_html": matched_by_html,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "withdrawn": withdrawn,
        "categories": category_rows,
        "cms_preserved_categories": cms_preserved_categories,
        "cms_preserved_category_products": cms_preserved_category_products,
        "cms_preserved_pdf_products": cms_preserved_pdf_products,
        "category_catalogues_synced": category_catalogues_synced,
        "documents_linked": resolved_with_pdfs,
        "message": (
            f"Synced {created + updated} WooCommerce products "
            f"({resolved_with_pdfs} with PDFs linked; {category_catalogues_synced} category catalogues mapped; "
            f"preserved {cms_preserved_categories} CMS collections and {cms_preserved_category_products} product category overrides)."
        ),
    }


@router.get("/products")
def wordpress_products(
    limit: int = Query(default=20, ge=1, le=50),
    admin: AdminIdentity = Depends(require_admin_roles(*ROLES)),
) -> dict[str, Any]:
    rows, settings = _fetch(limit)
    result = []
    for row in rows:
        source_id = _field(row, settings.wordpress_source_id_field, row.get("id"))
        result.append({
            "id": str(source_id),
            "title": _plain(_field(row, settings.wordpress_source_title_field, row.get("title", "")), 220),
            "slug": str(_field(row, settings.wordpress_source_slug_field, row.get("slug", "")))[:180],
            "summary": _plain(_field(row, settings.wordpress_source_summary_field, row.get("excerpt", ""))),
            "model_code": _plain(_field(row, settings.wordpress_source_model_field, ""), 120),
            "description": _plain(_field(row, settings.wordpress_source_description_field, ""), 500),
            "image_url": _image_url(_field(row, settings.wordpress_source_image_field)),
            "link": str(row.get("link", ""))[:1000],
        })
    return {"items": result, "message": f"Fetched {len(result)} WordPress records. These are previews; import creates drafts."}


@router.post("/import")
def import_wordpress_product(
    body: WordPressImport,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*ROLES)),
) -> dict[str, Any]:
    category = session.get(ProductCategory, body.category_id)
    if category is None:
        raise HTTPException(status_code=422, detail="Choose a valid catalogue category")
    rows, settings = _fetch(50)
    source = next((row for row in rows if str(_field(row, settings.wordpress_source_id_field, row.get("id"))) == body.source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="WordPress product was not found in the first 50 published records")
    wp_id = str(_field(source, settings.wordpress_source_id_field, source.get("id")))
    existing = session.query(Product).filter(Product.wordpress_source_id == wp_id).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This WordPress product has already been imported")
    title = _plain(_field(source, settings.wordpress_source_title_field, source.get("title", "")), 220)
    slug = str(_field(source, settings.wordpress_source_slug_field, source.get("slug", "")))[:180]
    if len(title) < 2 or not slug or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in slug):
        raise HTTPException(status_code=422, detail="WordPress title or slug is not valid for the catalogue")
    summary = _plain(_field(source, settings.wordpress_source_summary_field, source.get("excerpt", "")))
    model = _plain(_field(source, settings.wordpress_source_model_field, ""), 120)
    description = _plain(_field(source, settings.wordpress_source_description_field, ""), 12000, preserve_blocks=True)
    image_url = _image_url(_field(source, settings.wordpress_source_image_field))
    gallery = _field(source, settings.wordpress_source_gallery_field, [])
    gallery_images = list(dict.fromkeys(url for item in (gallery if isinstance(gallery, list) else []) if (url := _image_url(item)) and url != image_url))[:16]
    applications = _string_list(_field(source, settings.wordpress_source_applications_field, []), 24)
    features = _string_list(_field(source, settings.wordpress_source_features_field, []), 32)
    specifications = _specifications(_field(source, settings.wordpress_source_specifications_field, {}))
    link = str(source.get("link", ""))[:1000]
    values = {
        "category_id": str(category.id), "slug": slug, "name": title,
        "model_code": model or None, "summary": summary or None, "description": description or None,
        "applications": applications, "features": features, "specifications": specifications, "image_url": image_url,
        "gallery_images": gallery_images, "source_reference": link or None,
        "wordpress_source_id": wp_id, "wordpress_source_url": link or None,
    }
    product = Product(category_id=category.id, slug=slug, name=title, model_code=model or None, summary=summary or None, description=description or None, image_url=image_url, gallery_images=gallery_images, applications=applications, features=features, specifications=specifications, is_published=False, wordpress_source_id=wp_id, wordpress_source_url=link or None, draft_data=values)
    session.add(product)
    session.add(AuditEvent(actor_uid=admin.uid, action="product.imported_from_wordpress", entity_type="product", entity_id=str(product.id), change_summary={"source_id": wp_id, "source_url": link}))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A product with this slug or WordPress source ID already exists") from error
    return {"id": str(product.id), "name": title, "is_published": False, "message": "Imported as a draft. Verify technical facts and source before publishing."}
