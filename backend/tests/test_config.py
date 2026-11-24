from app.core.config import Settings


def test_woocommerce_standard_routes_and_mappings_have_code_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.wordpress_products_path == "wc/v3/products"
    assert settings.wordpress_categories_path == "wc/v3/products/categories"
    assert settings.wordpress_store_products_path == "wc/store/v1/products"
    assert settings.wordpress_documents_path == "wp/v2/media"
    assert settings.wordpress_source_applications_field == ""
    assert settings.wordpress_source_features_field == ""
