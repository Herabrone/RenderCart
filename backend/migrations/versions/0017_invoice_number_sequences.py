"""Add owner-scoped sequential invoice, quote, and receipt numbering."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_invoice_number_sequences"
down_revision: str | None = "0016_saved_invoice_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_number_sequences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=16), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "document_type", name="uq_invoice_number_owner_type"),
    )
    op.create_index("ix_invoice_number_sequences_user_id", "invoice_number_sequences", ["user_id"])


def downgrade() -> None:
    op.drop_table("invoice_number_sequences")
