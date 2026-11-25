from app.api.wordpress import _documents, _plain


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
    assert _documents(product, [], "acf.datasheets") == [
        {"title": "Technical datasheet", "url": "https://store.example.test/files/tech.pdf"},
        {"title": "Product datasheet", "url": "https://store.example.test/files/manual.pdf"},
    ]
