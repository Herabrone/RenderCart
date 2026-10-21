"""Add owned uptime monitors and check history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_uptime_monitors"
down_revision: str | None = "0019_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uptime_monitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("alert_email", sa.String(length=320), nullable=False),
        sa.Column("alert_webhook_enc", sa.String(length=4096), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_response_ms", sa.Integer(), nullable=True),
        sa.Column("last_error_code", sa.String(length=40), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("outage_alert_sent", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uptime_monitors_user_id", "uptime_monitors", ["user_id"])
    op.create_index("ix_uptime_monitors_due", "uptime_monitors", ["active", "next_check_at"])
    op.create_index("ix_uptime_monitors_owner", "uptime_monitors", ["user_id", "created_at"])
    op.create_index("ix_uptime_monitors_next_check_at", "uptime_monitors", ["next_check_at"])

    op.create_table(
        "uptime_monitor_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["monitor_id"], ["uptime_monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uptime_monitor_checks_monitor_id", "uptime_monitor_checks", ["monitor_id"])
    op.create_index(
        "ix_uptime_monitor_checks_monitor_time",
        "uptime_monitor_checks",
        ["monitor_id", "checked_at"],
    )
    op.create_index("ix_uptime_monitor_checks_checked_at", "uptime_monitor_checks", ["checked_at"])


def downgrade() -> None:
    op.drop_table("uptime_monitor_checks")
    op.drop_table("uptime_monitors")
