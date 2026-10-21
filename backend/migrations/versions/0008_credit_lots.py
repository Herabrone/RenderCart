"""Track credit grants as expiring lots and reserve job spending FIFO."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_credit_lots"
down_revision: str | None = "0007_job_payment_tier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_ledger_id", sa.Uuid(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("held", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_ledger_id"], ["credit_ledger.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_ledger_id"),
    )
    op.create_index("ix_credit_lots_user_id", "credit_lots", ["user_id"])
    op.create_index("ix_credit_lots_expires_at", "credit_lots", ["expires_at"])
    op.create_table(
        "credit_reservations",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("credit_lot_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credit_lot_id"], ["credit_lots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "credit_lot_id"),
    )
    # Existing negative spend/refund rows are allocated FIFO across historical
    # grants so the new lot balances start near the pre-migration aggregate.
    op.execute(
        """WITH grant_rows AS (
            SELECT
                id,
                user_id,
                amount,
                expires_at,
                created_at,
                SUM(amount) OVER (
                    PARTITION BY user_id ORDER BY created_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS grant_total,
                COALESCE((
                    SELECT SUM(-spent.amount)
                    FROM credit_ledger AS spent
                    WHERE spent.user_id = credit_ledger.user_id
                      AND spent.amount < 0
                ), 0) AS spent_total
            FROM credit_ledger
            WHERE amount > 0
        )
        INSERT INTO credit_lots
        (id, user_id, source_ledger_id, total, remaining, held, expires_at, created_at)
        SELECT
            id,
            user_id,
            id,
            amount,
            GREATEST(0, amount - GREATEST(0, spent_total - (grant_total - amount))),
            0,
            expires_at,
            created_at
        FROM grant_rows"""
    )


def downgrade() -> None:
    op.drop_table("credit_reservations")
    op.drop_index("ix_credit_lots_expires_at", table_name="credit_lots")
    op.drop_index("ix_credit_lots_user_id", table_name="credit_lots")
    op.drop_table("credit_lots")
