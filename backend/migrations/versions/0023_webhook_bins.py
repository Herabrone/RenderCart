"""Add expiring webhook request bins."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_webhook_bins"
down_revision: str | None = "0022_domain_expiry_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_bins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_webhook_bins_token_hash"),
    )
    op.create_index("ix_webhook_bins_user_id", "webhook_bins", ["user_id"])
    op.create_index("ix_webhook_bins_token_hash", "webhook_bins", ["token_hash"])
    op.create_index("ix_webhook_bins_expires_at", "webhook_bins", ["expires_at"])
    op.create_index("ix_webhook_bins_owner_expiry", "webhook_bins", ["user_id", "expires_at"])

    op.create_table(
        "webhook_bin_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bin_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("payload_enc", sa.Text(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["bin_id"], ["webhook_bins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_bin_events_bin_id", "webhook_bin_events", ["bin_id"])
    op.create_index(
        "ix_webhook_bin_events_bin_received", "webhook_bin_events", ["bin_id", "received_at"]
    )


def downgrade() -> None:
    op.drop_table("webhook_bin_events")
    op.drop_table("webhook_bins")
