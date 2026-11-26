"""Add FAQ image and video URL lists."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8b4f902c6d1"
down_revision: Union[str, None] = "b7e2f91c4a01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_articles", sa.Column("image_urls", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("knowledge_articles", sa.Column("video_urls", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("knowledge_articles", "video_urls")
    op.drop_column("knowledge_articles", "image_urls")
