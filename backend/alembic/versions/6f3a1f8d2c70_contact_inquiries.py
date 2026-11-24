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
    op.create_index("ix_contact_inquiries_email", "contact_inquiries", ["email"])
    op.create_index("ix_contact_inquiries_inquiry_type", "contact_inquiries", ["inquiry_type"])
    op.create_index("ix_contact_inquiries_status", "contact_inquiries", ["status"])
    op.create_index("ix_contact_inquiries_created_at", "contact_inquiries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_inquiries_created_at", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_status", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_inquiry_type", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_email", table_name="contact_inquiries")
    op.drop_table("contact_inquiries")
