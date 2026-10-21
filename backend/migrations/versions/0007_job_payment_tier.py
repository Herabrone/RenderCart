"""Record the selected single-job price tier on each pending job."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_job_payment_tier"
down_revision: str | None = "0006_paid_job_dispatch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("payment_tier", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "payment_tier")
