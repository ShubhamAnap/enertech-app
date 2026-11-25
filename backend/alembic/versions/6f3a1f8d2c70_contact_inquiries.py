"""Create customer contact inquiry storage.

Revision ID: 6f3a1f8d2c70
Revises: e21a7c0d9f43
Create Date: 2026-11-24
"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f3a1f8d2c70"
down_revision: Union[str, None] = "e21a7c0d9f43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("contact_inquiries"):
        op.create_table(
            "contact_inquiries",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("phone", sa.String(24), nullable=False),
            sa.Column("company_name", sa.String(220), nullable=True),
            sa.Column("subject", sa.String(220), nullable=True),
            sa.Column("message", sa.String(10000), nullable=False),
            sa.Column("inquiry_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)
    else:
        existing_columns = {column["name"] for column in inspector.get_columns("contact_inquiries")}
        required_columns = {
            "id", "name", "email", "phone", "company_name", "subject", "message",
            "inquiry_type", "status", "notes", "created_at", "updated_at",
        }
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            raise RuntimeError(
                "Existing contact_inquiries table is missing columns required by migration "
                f"{revision}: {', '.join(missing_columns)}. Reconcile the schema before deploying."
            )

    expected_indexes = {
        "ix_contact_inquiries_email": ["email"],
        "ix_contact_inquiries_inquiry_type": ["inquiry_type"],
        "ix_contact_inquiries_status": ["status"],
        "ix_contact_inquiries_created_at": ["created_at"],
    }
    existing_indexes = sa.inspect(bind).get_indexes("contact_inquiries")
    existing_index_names = {index["name"]: index.get("column_names") for index in existing_indexes}
    for name, columns in expected_indexes.items():
        if name in existing_index_names:
            if existing_index_names[name] != columns:
                raise RuntimeError(
                    f"Existing index {name} does not match the expected columns; reconcile it before deploying."
                )
        elif any(index.get("column_names") == columns for index in existing_indexes):
            # The legacy Supabase schema uses idx_* names for these same indexes.
            # Reuse an equivalent index instead of creating a redundant copy.
            continue
        else:
            op.create_index(name, "contact_inquiries", columns)


def downgrade() -> None:
    op.drop_index("ix_contact_inquiries_created_at", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_status", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_inquiry_type", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_email", table_name="contact_inquiries")
    op.drop_table("contact_inquiries")

