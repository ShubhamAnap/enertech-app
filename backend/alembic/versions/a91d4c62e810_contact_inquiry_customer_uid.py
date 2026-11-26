"""Associate contact inquiries with their authenticated customer.

Revision ID: a91d4c62e810
Revises: 6f3a1f8d2c70
Create Date: 2026-11-24
"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "a91d4c62e810"
down_revision: Union[str, None] = "6f3a1f8d2c70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("contact_inquiries")}
    if "customer_uid" not in columns:
        op.add_column("contact_inquiries", sa.Column("customer_uid", sa.String(length=128), nullable=True))

    indexes = sa.inspect(bind).get_indexes("contact_inquiries")
    indexes_by_name = {index["name"]: index.get("column_names") for index in indexes}
    index_name = "ix_contact_inquiries_customer_uid"
    if index_name in indexes_by_name:
        if indexes_by_name[index_name] != ["customer_uid"]:
            raise RuntimeError(f"Existing index {index_name} does not match the expected column.")
    elif any(index.get("column_names") == ["customer_uid"] for index in indexes):
        pass
    else:
        op.create_index(index_name, "contact_inquiries", ["customer_uid"])
    # Submissions already have a matching audit event with the authenticated UID.
    # Backfill it so inquiries from the previous deployment remain covered by
    # the account-based rate limit after an email address changes.
    if sa.inspect(bind).has_table("audit_events"):
        op.execute(sa.text(
            "UPDATE contact_inquiries AS inquiry "
            "SET customer_uid = audit.actor_uid "
            "FROM audit_events AS audit "
            "WHERE inquiry.customer_uid IS NULL "
            "AND audit.entity_type = 'contact_inquiry' "
            "AND audit.action = 'contact_inquiry.submitted' "
            "AND audit.entity_id = CAST(inquiry.id AS VARCHAR)"
        ))


def downgrade() -> None:
    op.drop_index("ix_contact_inquiries_customer_uid", table_name="contact_inquiries")
    op.drop_column("contact_inquiries", "customer_uid")
