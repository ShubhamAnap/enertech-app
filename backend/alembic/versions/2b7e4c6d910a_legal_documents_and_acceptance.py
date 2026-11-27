"""Store immutable legal publication versions and customer acceptance."""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "2b7e4c6d910a"
down_revision: Union[str, None] = "e8b4f902c6d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_document_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(100000), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key", "version", name="uq_legal_document_key_version"),
    )
    op.create_index("ix_legal_document_versions_key", "legal_document_versions", ["key"])
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("customer_uid", sa.String(128), nullable=False),
        sa.Column("privacy_version_id", sa.Uuid(), sa.ForeignKey("legal_document_versions.id"), nullable=False),
        sa.Column("terms_version_id", sa.Uuid(), sa.ForeignKey("legal_document_versions.id"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("customer_uid", "privacy_version_id", "terms_version_id", name="uq_customer_legal_versions"),
    )
    op.create_index("ix_legal_acceptances_customer_uid", "legal_acceptances", ["customer_uid"])


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_customer_uid", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
    op.drop_index("ix_legal_document_versions_key", table_name="legal_document_versions")
    op.drop_table("legal_document_versions")
