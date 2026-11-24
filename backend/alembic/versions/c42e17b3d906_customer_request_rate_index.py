"""Index customer requests for per-account rate checks.

Revision ID: c42e17b3d906
Revises: a91d4c62e810
Create Date: 2026-11-24
"""
from collections.abc import Sequence
from typing import Union

from alembic import op


revision: str = "c42e17b3d906"
down_revision: Union[str, None] = "a91d4c62e810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_customer_requests_customer_created",
        "customer_requests",
        ["customer_uid", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_requests_customer_created", table_name="customer_requests")

