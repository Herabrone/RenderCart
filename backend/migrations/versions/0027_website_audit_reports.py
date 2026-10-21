"""Persist summaries of completed website audits for Pro history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_website_audit_reports"
down_revision: str | None = "0026_monitor_sms_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website_audit_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("target_url_enc", sa.Text(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_website_audit_reports_job_id"),
    )
    op.create_index(
        "ix_website_audit_reports_user_id", "website_audit_reports", ["user_id"]
    )
    op.create_index(
        "ix_website_audit_reports_owner_created",
        "website_audit_reports",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("website_audit_reports")
