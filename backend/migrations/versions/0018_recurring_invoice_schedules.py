"""Store encrypted recurring invoice templates and execution state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_recurring_invoice_schedules"
down_revision: str | None = "0017_invoice_number_sequences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_invoice_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("anchor_day", sa.Integer(), nullable=False),
        sa.Column("encrypted_invoice_json", sa.String(length=32768), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_job_id", sa.Uuid(), nullable=True),
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
    op.create_index(
        "ix_recurring_invoice_schedules_user_id", "recurring_invoice_schedules", ["user_id"]
    )
    op.create_index(
        "ix_recurring_invoice_schedules_next_run_at", "recurring_invoice_schedules", ["next_run_at"]
    )
    op.create_index(
        "ix_recurring_invoice_due", "recurring_invoice_schedules", ["active", "next_run_at"]
    )


def downgrade() -> None:
    op.drop_table("recurring_invoice_schedules")
