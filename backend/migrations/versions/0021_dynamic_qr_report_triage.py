"""Add status and reviewer fields to dynamic QR abuse reports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_dynamic_qr_report_triage"
down_revision: str | None = "0020_uptime_monitors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dynamic_qr_reports",
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
    )
    op.add_column(
        "dynamic_qr_reports",
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "dynamic_qr_reports",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dynamic_qr_reports_resolved_by_users",
        "dynamic_qr_reports",
        "users",
        ["resolved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_dynamic_qr_reports_status_created",
        "dynamic_qr_reports",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dynamic_qr_reports_status_created", table_name="dynamic_qr_reports")
    op.drop_constraint(
        "fk_dynamic_qr_reports_resolved_by_users", "dynamic_qr_reports", type_="foreignkey"
    )
    op.drop_column("dynamic_qr_reports", "resolved_at")
    op.drop_column("dynamic_qr_reports", "resolved_by")
    op.drop_column("dynamic_qr_reports", "status")
