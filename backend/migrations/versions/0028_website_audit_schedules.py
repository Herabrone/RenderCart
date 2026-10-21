"""Add Pro weekly website-audit schedules."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_website_audit_schedules"
down_revision: str | None = "0027_website_audit_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website_audit_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target_url_enc", sa.Text(), nullable=False),
        sa.Column("device", sa.String(16), server_default="mobile", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_job_id", sa.Uuid(), nullable=True),
        sa.Column("last_error_code", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_website_audit_schedules_user_id", "website_audit_schedules", ["user_id"])
    op.create_index(
        "ix_website_audit_schedules_next_run_at", "website_audit_schedules", ["next_run_at"]
    )
    op.create_index(
        "ix_website_audit_schedules_due",
        "website_audit_schedules",
        ["active", "next_run_at"],
    )
    op.create_index(
        "ix_website_audit_schedules_owner_created",
        "website_audit_schedules",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("website_audit_schedules")
