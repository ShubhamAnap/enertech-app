"""Add Firebase-owned customer onboarding profiles."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "ca70b415d05b"
down_revision: Union[str, None] = "db62e92f3140"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("customer_type", sa.String(24), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("mobile_number", sa.String(24), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("location", sa.String(500), nullable=False),
        sa.Column("company_name", sa.String(220), nullable=True),
        sa.Column("gst_number", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_profiles_firebase_uid", "customer_profiles", ["firebase_uid"], unique=True)
    op.create_index("ix_customer_profiles_customer_type", "customer_profiles", ["customer_type"])


def downgrade() -> None:
    op.drop_index("ix_customer_profiles_customer_type", table_name="customer_profiles")
    op.drop_index("ix_customer_profiles_firebase_uid", table_name="customer_profiles")
    op.drop_table("customer_profiles")
