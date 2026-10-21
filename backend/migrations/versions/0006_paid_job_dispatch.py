"""Add the transactional outbox used to dispatch paid jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_paid_job_dispatch"
down_revision: str | None = "0005_stripe_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_dispatches",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_job_dispatches_dispatched_at", "job_dispatches", ["dispatched_at"])


def downgrade() -> None:
    op.drop_index("ix_job_dispatches_dispatched_at", table_name="job_dispatches")
    op.drop_table("job_dispatches")
