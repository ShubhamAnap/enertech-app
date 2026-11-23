"""Add publishable, source-referenced customer knowledge articles."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "db62e92f3140"
down_revision: Union[str, None] = "9bc3d5062a71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("title", sa.String(220), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("answer", sa.String(12000), nullable=False),
        sa.Column("source_reference", sa.String(1000), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("draft_data", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_articles_slug", "knowledge_articles", ["slug"], unique=True)
    op.create_index("ix_knowledge_articles_category", "knowledge_articles", ["category"])
    op.create_index("ix_knowledge_articles_is_published", "knowledge_articles", ["is_published"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_is_published", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_articles_category", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_articles_slug", table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
