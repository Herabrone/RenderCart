"""Store paid full-resolution results separately from free previews."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_locked_job_outputs"
down_revision: str | None = "0010_ai_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("locked_output_key", sa.String(length=512), nullable=True))
    op.add_column("jobs", sa.Column("locked_output_filename", sa.String(length=255), nullable=True))
    op.add_column(
        "jobs", sa.Column("locked_output_content_type", sa.String(length=127), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("jobs", "locked_output_content_type")
    op.drop_column("jobs", "locked_output_filename")
    op.drop_column("jobs", "locked_output_key")
