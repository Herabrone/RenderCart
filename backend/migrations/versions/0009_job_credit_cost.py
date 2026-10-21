"""Persist the credit amount reserved for each job at submit time."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_job_credit_cost"
down_revision: str | None = "0008_credit_lots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("charged_credits", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("jobs", "charged_credits")
