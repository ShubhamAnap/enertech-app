"""Add WooCommerce source, price, stock, and product document fields."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "e21a7c0d9f43"
down_revision: Union[str, None] = "ca70b415d05b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_categories", sa.Column("wordpress_source_id", sa.String(160), nullable=True))
    op.create_index("ix_product_categories_wordpress_source_id", "product_categories", ["wordpress_source_id"], unique=True)
    op.add_column("products", sa.Column("price_minor", sa.BigInteger(), nullable=True))
    op.add_column("products", sa.Column("currency_code", sa.String(3), server_default="INR", nullable=False))
    op.add_column("products", sa.Column("currency_minor_unit", sa.Integer(), server_default="2", nullable=False))
    op.add_column("products", sa.Column("stock_status", sa.String(24), server_default="unknown", nullable=False))
    op.add_column("products", sa.Column("stock_quantity", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("documents", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
    op.create_index("ix_products_stock_status", "products", ["stock_status"])


def downgrade() -> None:
    op.drop_index("ix_products_stock_status", table_name="products")
    op.drop_column("products", "documents")
    op.drop_column("products", "stock_quantity")
    op.drop_column("products", "stock_status")
    op.drop_column("products", "currency_code")
    op.drop_column("products", "currency_minor_unit")
    op.drop_column("products", "price_minor")
    op.drop_index("ix_product_categories_wordpress_source_id", table_name="product_categories")
    op.drop_column("product_categories", "wordpress_source_id")
