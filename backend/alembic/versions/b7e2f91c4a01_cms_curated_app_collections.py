"""Separate CMS-curated app collections from hidden WordPress source tags."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e2f91c4a01"
down_revision: Union[str, None] = "9a8c4e2d1b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column("is_app_collection", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(
        "ix_product_categories_is_app_collection",
        "product_categories",
        ["is_app_collection"],
    )
    # Keep imported WooCommerce categories purely as internal WP reference tags;
    # only CMS-curated app collections should be published to customers.
    op.execute(
        sa.text(
            "UPDATE product_categories "
            "SET is_app_collection = false, is_published = false "
            "WHERE wordpress_source_id IS NOT NULL OR "
            "(slug = 'uncategorized' AND name = 'Uncategorized' AND "
            "description = 'Products without a WooCommerce category.' AND NOT is_published AND draft_data IS NULL)"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_product_categories_is_app_collection", table_name="product_categories")
    op.drop_column("product_categories", "is_app_collection")
