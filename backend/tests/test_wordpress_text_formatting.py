from app.api.wordpress import _plain


def test_plain_description_keeps_html_paragraphs_headings_and_lists_readable() -> None:
    value = "<h2>Product Overview</h2><p>Solar and battery control.</p><h3>Key Features</h3><ul><li>No-break changeover</li><li>Battery modes</li></ul>"

    assert _plain(value, 1000, preserve_blocks=True) == (
        "Product Overview\nSolar and battery control.\nKey Features\n• No-break changeover\n• Battery modes"
    )


def test_plain_text_still_collapses_html_for_single_line_fields() -> None:
    assert _plain("<p>EnerTech</p><p>UPS</p>") == "EnerTech UPS"

