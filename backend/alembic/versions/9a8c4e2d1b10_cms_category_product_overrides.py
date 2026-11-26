"""Add CMS override lock flags for WordPress categories, product collections, and PDFs."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "9a8c4e2d1b10"
down_revision: Union[str, None] = "f4c2b8a19d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column("cms_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("category_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("documents_override", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("products", "documents_override")
    op.drop_column("products", "category_override")
    op.drop_column("product_categories", "cms_locked")
