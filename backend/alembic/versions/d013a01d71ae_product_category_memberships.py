"""Preserve every product category imported from WooCommerce."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "d013a01d71ae"
down_revision: Union[str, None] = "c42e17b3d906"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_category_links",
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("product_categories.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute(sa.text(
        "INSERT INTO product_category_links (product_id, category_id) "
        "SELECT id, category_id FROM products WHERE category_id IS NOT NULL"
    ))


def downgrade() -> None:
    op.drop_table("product_category_links")
