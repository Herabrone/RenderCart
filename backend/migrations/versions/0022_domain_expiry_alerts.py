"""Add TLS certificate and RDAP expiry alerts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_domain_expiry_alerts"
down_revision: str | None = "0021_dynamic_qr_report_triage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_expiry_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("alert_email", sa.String(length=320), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tls_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("domain_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tls_error_code", sa.String(length=40), nullable=True),
        sa.Column("domain_error_code", sa.String(length=40), nullable=True),
        sa.Column("tls_alerted_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("domain_alerted_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_expiry_alerts_user_id", "domain_expiry_alerts", ["user_id"])
    op.create_index(
        "ix_domain_expiry_alerts_due", "domain_expiry_alerts", ["active", "next_check_at"]
    )
    op.create_index(
        "ix_domain_expiry_alerts_owner", "domain_expiry_alerts", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_domain_expiry_alerts_next_check_at", "domain_expiry_alerts", ["next_check_at"]
    )


def downgrade() -> None:
    op.drop_table("domain_expiry_alerts")
