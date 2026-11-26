from types import SimpleNamespace
import httpx
import pytest

import app.api.wordpress as wordpress_api
from app.api.wordpress import (
    _documents,
    _extract_html_pdf_documents,
    _fetch_all,
    _fetch_pdf_media_resilient,
    _https_url,
    _normalize_wp_base_url,
    _plain,
    _safe_json,
    _sanitize_log_snippet,
    _sanitize_url_for_log,
)


def test_plain_description_keeps_html_paragraphs_headings_and_lists_readable() -> None:
    value = "<h2>Product Overview</h2><p>Solar and battery control.</p><h3>Key Features</h3><ul><li>No-break changeover</li><li>Battery modes</li></ul>"

    assert _plain(value, 1000, preserve_blocks=True) == (
        "Product Overview\nSolar and battery control.\nKey Features\n• No-break changeover\n• Battery modes"
    )


def test_plain_text_still_collapses_html_for_single_line_fields() -> None:
    assert _plain("<p>EnerTech</p><p>UPS</p>") == "EnerTech UPS"


def test_plain_description_decodes_double_encoded_wordpress_entities() -> None:
    value = "Output &amp;amp; overload &amp;lt;3%"

    assert _plain(value, 1000, preserve_blocks=True) == "Output & overload <3%"


def test_product_documents_include_configured_custom_field_urls() -> None:
    product = {
        "id": 42,
        "acf": {"datasheets": [
            {"title": "Technical datasheet", "url": "https://store.example.test/files/tech.pdf"},
            "https://store.example.test/files/manual.pdf",
        ]},
    }
    docs = _documents(product, [], "acf.datasheets")
    assert docs == [
        {"title": "Technical datasheet", "url": "https://store.example.test/files/tech.pdf"},
        {"title": "Product datasheet", "url": "https://store.example.test/files/manual.pdf"},
    ]


def test_product_documents_use_woocommerce_meta_and_description_links() -> None:
    product = {
        "id": 43,
        "meta_data": [
            {"key": "_product_catalogue_pdf", "value": "https://store.example.test/files/catalogue.pdf?download=1"},
            {"key": "_unrelated_note", "value": "https://store.example.test/files/not-a-catalogue.pdf"},
        ],
        "description": '<p>Details <a href="https://store.example.test/files/technical-sheet.pdf?ver=2">PDF</a></p>',
        "short_description": "See https://store.example.test/files/short.pdf for specifications.",
    }
    docs = _documents(product, [])
    assert docs == [
        {"title": "product catalogue pdf", "url": "https://store.example.test/files/catalogue.pdf?download=1"},
        {"title": "Product datasheet", "url": "https://store.example.test/files/technical-sheet.pdf?ver=2"},
        {"title": "Product datasheet", "url": "https://store.example.test/files/short.pdf"},
    ]


def test_product_documents_include_only_pdf_media_attached_to_product() -> None:
    media = [
        {"post": 44, "mime_type": "application/pdf", "source_url": "https://store.example.test/files/attached.pdf", "title": {"rendered": "Attached brochure"}},
        {"parent": 44, "mime_type": "application/pdf", "source_url": "https://store.example.test/files/parent.pdf", "title": {"rendered": "Product catalogue"}},
        {"post": 44, "mime_type": "image/png", "source_url": "https://store.example.test/files/image.png"},
        {"post": 45, "mime_type": "application/pdf", "source_url": "https://store.example.test/files/other-product.pdf"},
    ]
    assert _documents({"id": 44}, media) == [
        {"title": "Attached brochure", "url": "https://store.example.test/files/attached.pdf"},
        {"title": "Product catalogue", "url": "https://store.example.test/files/parent.pdf"},
    ]


def test_documents_resolve_attachment_ids_and_relative_pdf_urls() -> None:
    media = [
        {"id": 88, "mime_type": "application/pdf", "source_url": "https://enertechups.com/wp-content/uploads/sunmagic.pdf", "title": {"rendered": "SunMagic Brochure"}},
    ]
    product = {
        "id": 3919,
        "meta_data": [{"key": "download_brochure", "value": "88"}],
        "description": '<a href="/wp-content/uploads/local-sheet.pdf">Download Brochure</a>',
    }
    docs = _documents(product, media, site_origin="https://enertechups.com")
    assert docs == [
        {"title": "SunMagic Brochure", "url": "https://enertechups.com/wp-content/uploads/sunmagic.pdf"},
        {"title": "Product datasheet", "url": "https://enertechups.com/wp-content/uploads/local-sheet.pdf"},
    ]


def test_safe_json_handles_bom_prepended_html_and_trailing_php_notices() -> None:
    raw = (
        "\ufeff<!-- cached by litespeed --><style>body{margin:0}</style>"
        '[{"id": 10, "name": "Batteryless Solar Hybrid Inverter"}]'
        "<br/><b>Notice</b>: undefined index in {plugin}"
    )
    response = httpx.Response(200, text=raw, headers={"content-type": "application/json; charset=utf-8"})
    parsed = _safe_json(response, expect_list=True)
    assert parsed == [{"id": 10, "name": "Batteryless Solar Hybrid Inverter"}]


def test_normalize_wp_base_url_and_secret_redaction() -> None:
    assert _normalize_wp_base_url("https://enertechups.com/", "production") == "https://enertechups.com/wp-json"
    assert _normalize_wp_base_url("https://enertechups.com/wp-json/", "production") == "https://enertechups.com/wp-json"
    redacted_url = _sanitize_url_for_log("https://enertechups.com/wp-json/wc/v3/products?consumer_key=ck_secret_1&consumer_secret=cs_secret_2&page=1")
    assert "ck_secret_1" not in redacted_url
    assert "cs_secret_2" not in redacted_url
    snippet = _sanitize_log_snippet("error echo ck_secret_1 failed", secrets=("ck_secret_1",))
    assert "ck_secret_1" not in snippet
    assert "***" in snippet


def test_fetch_all_falls_back_to_query_auth_on_401_and_smaller_page_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://store.example.test/wp-json",
        wordpress_consumer_key="ck_test_key",
        wordpress_consumer_secret="cs_test_secret",
        wordpress_per_page=20,
    )
    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)
    calls: list[dict[str, object]] = []

    def fake_get(self, url, *, params=None, headers=None, auth=None):
        calls.append({"url": url, "params": dict(params or {}), "auth": auth})
        if auth is not None:
            return httpx.Response(401, request=httpx.Request("GET", url), text='{"code":"woocommerce_rest_cannot_view"}')
        if int((params or {}).get("per_page", 20)) > 10:
            return httpx.Response(500, request=httpx.Request("GET", url), text="Allowed memory size exhausted")
        return httpx.Response(200, request=httpx.Request("GET", url), text='[{"id": 1, "name": "UPS"}]')

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    rows = _fetch_all("wc/v3/products", authenticated=True)
    assert rows == [{"id": 1, "name": "UPS"}]
    assert calls[0]["auth"] == ("ck_test_key", "cs_test_secret")
    assert calls[1]["params"]["consumer_key"] == "ck_test_key"
    assert calls[2]["params"]["per_page"] == 10


def test_documents_upgrade_http_and_extract_escaped_elementor_and_downloads() -> None:
    product = {
        "id": 3919,
        "downloads": [
            {"name": "Batteryless Download", "file": "http://enertechups.com/wp-content/uploads/2025/05/bl-download"},
        ],
        "meta_data": [
            {
                "key": "_elementor_data",
                "value": '[{"settings":{"url":"http:\\/\\/enertechups.com\\/wp-content\\/uploads\\/2025\\/05\\/elementor-brochure.pdf"}}]',
            },
        ],
        "description": '<p><a href="http://enertechups.com/wp-content/uploads/desc-spec.pdf">Download</a></p>',
    }
    media = [
        {
            "id": 500,
            "post": 3919,
            "mime_type": "application/pdf",
            "title": {"rendered": "Attached Sheet"},
            "source_url": "http://enertechups.com/wp-content/uploads/attached-sheet.pdf",
        }
    ]
    docs = _documents(product, media, site_origin="https://enertechups.com")
    urls = [doc["url"] for doc in docs]
    assert "https://enertechups.com/wp-content/uploads/2025/05/bl-download" in urls
    assert "https://enertechups.com/wp-content/uploads/2025/05/elementor-brochure.pdf" in urls
    assert "https://enertechups.com/wp-content/uploads/desc-spec.pdf" in urls
    assert "https://enertechups.com/wp-content/uploads/attached-sheet.pdf" in urls
    assert _https_url("wp-content/uploads/a.pdf", site_origin="https://enertechups.com") == (
        "https://enertechups.com/wp-content/uploads/a.pdf"
    )


def test_fetch_pdf_media_resilient_keeps_partial_pages_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        app_env="production",
        wordpress_api_base_url="https://enertechups.com/wp-json",
        wordpress_consumer_key="ck_test",
        wordpress_consumer_secret="cs_test",
        wordpress_username="",
        wordpress_application_password="",
    )
    monkeypatch.setattr(wordpress_api, "get_settings", lambda: settings)

    def fake_get(self, url, *, params=None, headers=None, auth=None):
        p = dict(params or {})
        page = int(p.get("page", 1))
        per_page = int(p.get("per_page", 100))
        if per_page == 100:
            return httpx.Response(400, request=httpx.Request("GET", url), text='{"code":"rest_invalid_param"}')
        if page == 1 and "consumer_key" not in p:
            return httpx.Response(401, request=httpx.Request("GET", url), text='{"code":"rest_forbidden"}')
        if page == 1:
            batch = [{"id": idx, "source_url": f"http://enertechups.com/wp-content/uploads/doc-{idx}.pdf"} for idx in range(25)]
            return httpx.Response(200, request=httpx.Request("GET", url), json=batch, headers={"X-WP-TotalPages": "3"})
        return httpx.Response(500, request=httpx.Request("GET", url), text="Server busy")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    rows, status_note = _fetch_pdf_media_resilient("wp/v2/media")
    assert len(rows) == 25
    assert status_note == "partial_http_500:25"


def test_extract_html_pdf_documents_strips_header_nav_footer() -> None:
    html = """
    <html>
      <body>
        <header><nav><a href="/wp-content/uploads/global-header-catalog.pdf">Catalog</a></nav></header>
        <main>
          <h1>Batteryless Solar Hybrid Inverter</h1>
          <a href="http://enertechups.com/wp-content/uploads/batteryless-brochure.pdf">Download Brochure</a>
        </main>
        <footer><a href="https://enertechups.com/wp-content/uploads/footer-all-products.pdf">All PDF</a></footer>
      </body>
    </html>
    """
    docs = _extract_html_pdf_documents(html, site_origin="https://enertechups.com")
    assert docs == [
        {
            "title": "Product brochure",
            "url": "https://enertechups.com/wp-content/uploads/batteryless-brochure.pdf",
        }
    ]

    no_brochure_html = """
    <html><body>
      <header><a href="https://enertechups.com/wp-content/uploads/global-menu.pdf">Catalog</a></header>
      <main><h1>10KVA Voltage Stabilizer</h1><p>No brochure</p></main>
      <footer><a href="https://enertechups.com/wp-content/uploads/footer.pdf">Footer</a></footer>
    </body></html>
    """
    assert _extract_html_pdf_documents(no_brochure_html, site_origin="https://enertechups.com") == []
