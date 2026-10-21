"""Track per-job reservations against daily extracted-word quotas."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_word_quota_reservations"
down_revision: str | None = "0013_document_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("word_quota_key", sa.String(length=255), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("word_quota_reserved_words", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("jobs", "word_quota_reserved_words")
    op.drop_column("jobs", "word_quota_key")
