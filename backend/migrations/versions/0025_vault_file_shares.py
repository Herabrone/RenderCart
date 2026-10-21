"""Add encrypted expiring Vault file shares."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_vault_file_shares"
down_revision: str | None = "0024_vault_personal_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_file_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("object_key_enc", sa.Text(), nullable=False),
        sa.Column("filename_enc", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_vault_file_shares_code"),
    )
    op.create_index("ix_vault_file_shares_created_by", "vault_file_shares", ["created_by"])
    op.create_index("ix_vault_file_shares_expires_at", "vault_file_shares", ["expires_at"])


def downgrade() -> None:
    op.drop_table("vault_file_shares")
