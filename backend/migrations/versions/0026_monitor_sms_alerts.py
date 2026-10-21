"""Add opt-in, credit-metered uptime monitor SMS alerts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_monitor_sms_alerts"
down_revision: str | None = "0025_vault_file_shares"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("uptime_monitors", sa.Column("alert_sms_enc", sa.String(4096), nullable=True))
    op.add_column(
        "uptime_monitors",
        sa.Column("alert_sms_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "uptime_monitors",
        sa.Column("outage_generation", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "uptime_monitor_sms_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period", name="uq_uptime_monitor_sms_usage_owner_period"),
    )
    op.create_index("ix_uptime_monitor_sms_usage_user_id", "uptime_monitor_sms_usage", ["user_id"])
    op.create_table(
        "uptime_monitor_sms_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=True),
        sa.Column("outage_generation", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("credit_lot_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitor_id"], ["uptime_monitors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["credit_lot_id"], ["credit_lots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "monitor_id", "outage_generation", "event", name="uq_monitor_sms_delivery_event"
        ),
    )
    op.create_index(
        "ix_uptime_monitor_sms_deliveries_user_id", "uptime_monitor_sms_deliveries", ["user_id"]
    )
    op.create_index(
        "ix_uptime_monitor_sms_deliveries_monitor_id",
        "uptime_monitor_sms_deliveries",
        ["monitor_id"],
    )
    op.create_index(
        "ix_monitor_sms_delivery_user_created",
        "uptime_monitor_sms_deliveries",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("uptime_monitor_sms_deliveries")
    op.drop_table("uptime_monitor_sms_usage")
    op.drop_column("uptime_monitors", "outage_generation")
    op.drop_column("uptime_monitors", "alert_sms_consent_at")
    op.drop_column("uptime_monitors", "alert_sms_enc")
