"""Add encrypted super-admin Vault links and pastes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_vault_personal_tools"
down_revision: str | None = "0023_webhook_bins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vault_short_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("target_url_enc", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_vault_short_links_code"),
    )
    op.create_index("ix_vault_short_links_created_by", "vault_short_links", ["created_by"])
    op.create_index("ix_vault_short_links_expires_at", "vault_short_links", ["expires_at"])

    op.create_table(
        "vault_pastes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("content_enc", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_vault_pastes_code"),
    )
    op.create_index("ix_vault_pastes_created_by", "vault_pastes", ["created_by"])
    op.create_index("ix_vault_pastes_expires_at", "vault_pastes", ["expires_at"])


def downgrade() -> None:
    op.drop_table("vault_pastes")
    op.drop_table("vault_short_links")
