from app.api.wordpress import _documents


def test_product_documents_resolve_downloads_meta_description_and_attached_media() -> None:
    product = {
        "id": 42,
        "downloads": [{"name": "User guide", "file": "https://store.example.test/user-guide.pdf"}],
        "meta_data": [{"key": "_catalogue_pdf", "value": "https://store.example.test/catalogue.pdf?download=1"}],
        "description": '<a href="https://store.example.test/technical-sheet.pdf">Technical sheet</a>',
        "short_description": "More details: https://store.example.test/quick-spec.pdf",
    }
    media = [
        {"post": 42, "mime_type": "application/pdf", "source_url": "https://store.example.test/attached.pdf", "title": {"rendered": "Attached brochure"}},
        {"post": 42, "mime_type": "image/png", "source_url": "https://store.example.test/image.png"},
        {"post": 99, "mime_type": "application/pdf", "source_url": "https://store.example.test/other-product.pdf"},
    ]

    docs = _documents(product, media)

    assert docs == [
        {"title": "User guide", "url": "https://store.example.test/user-guide.pdf"},
        {"title": "_catalogue pdf", "url": "https://store.example.test/catalogue.pdf?download=1"},
        {"title": "Product datasheet", "url": "https://store.example.test/technical-sheet.pdf"},
        {"title": "Product datasheet", "url": "https://store.example.test/quick-spec.pdf"},
        {"title": "Attached brochure", "url": "https://store.example.test/attached.pdf"},
    ]
