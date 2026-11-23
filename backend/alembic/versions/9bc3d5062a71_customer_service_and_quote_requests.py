"""Add owned customer service and quote requests."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "9bc3d5062a71"
down_revision: Union[str, None] = "403b5a7c7647"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_uid", sa.String(128), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("resolution_note", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_requests_customer_uid", "customer_requests", ["customer_uid"])
    op.create_index("ix_customer_requests_kind", "customer_requests", ["kind"])
    op.create_index("ix_customer_requests_status", "customer_requests", ["status"])
    op.create_index("ix_customer_requests_assigned_to", "customer_requests", ["assigned_to"])
    op.create_index("ix_customer_requests_created_at", "customer_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_customer_requests_created_at", table_name="customer_requests")
    op.drop_index("ix_customer_requests_assigned_to", table_name="customer_requests")
    op.drop_index("ix_customer_requests_status", table_name="customer_requests")
    op.drop_index("ix_customer_requests_kind", table_name="customer_requests")
    op.drop_index("ix_customer_requests_customer_uid", table_name="customer_requests")
    op.drop_table("customer_requests")
