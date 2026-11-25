from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "EnerTech Customer Platform API"
    database_url: str = ""
    supabase_database_url: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_public_media_bucket: str = "enertech-public"
    api_cors_origins: str = ""
    firebase_project_id: str = ""
    firebase_service_account_json: str = ""
    firebase_auth_emulator_host: str = ""
    bootstrap_super_admin_uids: str = ""
    wordpress_api_base_url: str = ""
    wordpress_products_path: str = "wc/v3/products"
    wordpress_categories_path: str = "wc/v3/products/categories"
    wordpress_store_products_path: str = "wc/store/v1/products"
    wordpress_documents_path: str = "wp/v2/media"
    wordpress_consumer_key: str = ""
    wordpress_consumer_secret: str = ""
    wordpress_username: str = ""
    wordpress_application_password: str = ""
    wordpress_source_id_field: str = "id"
    wordpress_source_slug_field: str = "slug"
    wordpress_source_title_field: str = "name"
    wordpress_source_summary_field: str = "short_description"
    wordpress_source_model_field: str = "sku"
    wordpress_source_description_field: str = "description"
    wordpress_source_image_field: str = "images.0.src"
    wordpress_source_gallery_field: str = "images"
    wordpress_source_applications_field: str = ""
    wordpress_source_features_field: str = ""
    wordpress_source_specifications_field: str = "attributes"
    wordpress_source_documents_field: str = ""
    chat_allowed_hosts: str = ""
    chat_widget_script_url: str = ""
    # This value is sent to the customer app, so only a provider's public
    # browser/embed key may be configured here. Never use a server secret.
    chat_widget_public_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def active_database_url(self) -> str:
        return self.supabase_database_url.strip() or self.database_url.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def bootstrap_admin_uids(self) -> set[str]:
        return {uid.strip() for uid in self.bootstrap_super_admin_uids.split(",") if uid.strip()}

    @property
    def allowed_chat_hosts(self) -> set[str]:
        return {host.strip().lower() for host in self.chat_allowed_hosts.split(",") if host.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
