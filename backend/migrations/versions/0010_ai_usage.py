"""Persist AI provider usage and fallback spend."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_ai_usage"
down_revision: str | None = "0009_job_credit_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_spend_windows",
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(12, 6), nullable=False),
        sa.PrimaryKeyConstraint("month_start"),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("task", sa.String(length=80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("gpu_seconds", sa.Numeric(12, 4), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("job_id", "provider", "task", "fallback_used", "created_at"):
        op.create_index(f"ix_ai_usage_{column}", "ai_usage", [column])


def downgrade() -> None:
    for column in ("created_at", "fallback_used", "task", "provider", "job_id"):
        op.drop_index(f"ix_ai_usage_{column}", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_table("ai_spend_windows")
