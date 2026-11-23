"""cms app content and admin access

Revision ID: 403b5a7c7647
Revises: 0001_catalogue_foundation
Create Date: 2026-11-23 14:15:10.432085
"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = '403b5a7c7647'
down_revision: Union[str, None] = '0001_catalogue_foundation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_categories", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("product_categories", sa.Column("draft_data", sa.JSON(), nullable=True))

    op.add_column("products", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("applications", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("products", sa.Column("features", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("products", sa.Column("specifications", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("gallery_images", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("products", sa.Column("wordpress_source_id", sa.String(160), nullable=True))
    op.create_unique_constraint("uq_products_wordpress_source_id", "products", ["wordpress_source_id"])
    op.add_column("products", sa.Column("wordpress_source_url", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("source_reference", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("content_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("draft_data", sa.JSON(), nullable=True))
    op.alter_column("products", "applications", server_default=None)
    op.alter_column("products", "features", server_default=None)
    op.alter_column("products", "specifications", server_default=None)
    op.alter_column("products", "gallery_images", server_default=None)

    op.create_table(
        "admin_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("display_name", sa.String(180), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid", name="uq_admin_accounts_firebase_uid"),
    )
    op.create_index("ix_admin_accounts_firebase_uid", "admin_accounts", ["firebase_uid"], unique=True)
    op.create_index("ix_admin_accounts_role", "admin_accounts", ["role"])
    op.create_index("ix_admin_accounts_is_active", "admin_accounts", ["is_active"])

    op.create_table(
        "app_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("published_payload", sa.JSON(), nullable=True),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("published_by", sa.String(128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_app_config_key"),
    )
    op.create_index("ix_app_config_key", "app_config", ["key"], unique=True)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_uid", sa.String(128), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(160), nullable=False),
        sa.Column("change_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_actor_uid", "audit_events", ["actor_uid"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    # The initial schema created redundant unique indexes in addition to
    # unique constraints. Drop those indexes so metadata and migrations agree.
    op.drop_index("ix_product_categories_slug", table_name="product_categories")
    op.drop_index("ix_products_slug", table_name="products")


def downgrade() -> None:
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_product_categories_slug", "product_categories", ["slug"], unique=True)
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_type", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_uid", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_app_config_key", table_name="app_config")
    op.drop_table("app_config")
    op.drop_index("ix_admin_accounts_is_active", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_role", table_name="admin_accounts")
    op.drop_index("ix_admin_accounts_firebase_uid", table_name="admin_accounts")
    op.drop_table("admin_accounts")
    op.drop_column("products", "draft_data")
    op.drop_column("products", "content_verified_at")
    op.drop_column("products", "source_reference")
    op.drop_column("products", "wordpress_source_url")
    op.drop_constraint("uq_products_wordpress_source_id", "products", type_="unique")
    op.drop_column("products", "wordpress_source_id")
    op.drop_column("products", "gallery_images")
    op.drop_column("products", "image_url")
    op.drop_column("products", "specifications")
    op.drop_column("products", "features")
    op.drop_column("products", "applications")
    op.drop_column("products", "description")
    op.drop_column("product_categories", "draft_data")
    op.drop_column("product_categories", "image_url")
