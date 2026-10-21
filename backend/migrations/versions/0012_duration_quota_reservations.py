"""Track monthly duration quota reservations on jobs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_duration_quota_reservations"
down_revision: str | None = "0011_locked_job_outputs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("duration_quota_key", sa.String(length=255), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "duration_quota_reserved_seconds", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "duration_quota_reserved_seconds")
    op.drop_column("jobs", "duration_quota_key")
