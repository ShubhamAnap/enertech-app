"""Index customer requests for per-account rate checks.

Revision ID: c42e17b3d906
Revises: a91d4c62e810
Create Date: 2026-11-24
"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "c42e17b3d906"
down_revision: Union[str, None] = "a91d4c62e810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    indexes = {
        index["name"]: index.get("column_names")
        for index in sa.inspect(bind).get_indexes("customer_requests")
    }
    index_name = "ix_customer_requests_customer_created"
    expected_columns = ["customer_uid", "created_at"]
    if index_name in indexes:
        if indexes[index_name] != expected_columns:
            raise RuntimeError(f"Existing index {index_name} does not match the expected columns.")
    else:
        op.create_index(index_name, "customer_requests", expected_columns)


def downgrade() -> None:
    op.drop_index("ix_customer_requests_customer_created", table_name="customer_requests")
