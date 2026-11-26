"""Add category catalogue PDF mapping table for inheritance."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4c2b8a19d30"
down_revision: Union[str, None] = "d013a01d71ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_category_catalogues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category_key", sa.String(180), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("wordpress_category_id", sa.String(160), nullable=True),
        sa.Column("title", sa.String(180), server_default="Category catalogue PDF", nullable=False),
        sa.Column("catalog_pdf_url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(40), server_default="cms", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_category_catalogues_category_key", "product_category_catalogues", ["category_key"], unique=True)
    op.create_index("ix_product_category_catalogues_category_id", "product_category_catalogues", ["category_id"])
    op.create_index("ix_product_category_catalogues_wordpress_category_id", "product_category_catalogues", ["wordpress_category_id"])


def downgrade() -> None:
    op.drop_index("ix_product_category_catalogues_wordpress_category_id", table_name="product_category_catalogues")
    op.drop_index("ix_product_category_catalogues_category_id", table_name="product_category_catalogues")
    op.drop_index("ix_product_category_catalogues_category_key", table_name="product_category_catalogues")
    op.drop_table("product_category_catalogues")
