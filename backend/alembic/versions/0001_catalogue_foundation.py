"""Create initial catalogue tables."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_catalogue_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True), sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_index("ix_product_categories_slug", "product_categories", ["slug"], unique=True)
    op.create_index("ix_product_categories_is_published", "product_categories", ["is_published"])
    op.create_table("products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False), sa.Column("name", sa.String(220), nullable=False),
        sa.Column("model_code", sa.String(120), nullable=True), sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_model_code", "products", ["model_code"])
    op.create_index("ix_products_is_published", "products", ["is_published"])


def downgrade() -> None:
    for index in ("ix_products_is_published", "ix_products_model_code", "ix_products_slug", "ix_products_category_id"):
        op.drop_index(index, table_name="products")
    op.drop_table("products")
    op.drop_index("ix_product_categories_is_published", table_name="product_categories")
    op.drop_index("ix_product_categories_slug", table_name="product_categories")
    op.drop_table("product_categories")
