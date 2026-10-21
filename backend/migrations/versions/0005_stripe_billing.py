"""Persist Stripe customer, subscription, purchase, event, and credit expiry data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_stripe_billing"
down_revision: str | None = "0004_jobs_and_credits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=True)
    op.add_column("credit_ledger", sa.Column("reference_id", sa.String(255), nullable=True))
    op.add_column(
        "credit_ledger", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("credit_ledger", sa.Column("note", sa.String(255), nullable=True))
    op.create_index("ix_credit_ledger_expires_at", "credit_ledger", ["expires_at"])
    op.create_index("ix_credit_ledger_reference_id", "credit_ledger", ["reference_id"], unique=True)
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    for name, col in (
        ("user_id", "user_id"),
        ("stripe_subscription_id", "stripe_subscription_id"),
        ("stripe_customer_id", "stripe_customer_id"),
        ("status", "status"),
        ("current_period_end", "current_period_end"),
    ):
        op.create_index(
            f"ix_subscriptions_{name}",
            "subscriptions",
            [col],
            unique=name == "stripe_subscription_id",
        )
    op.create_table(
        "day_passes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("guest_id", sa.String(64), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_payment_intent_id"),
    )
    for name in ("user_id", "guest_id", "starts_at", "ends_at"):
        op.create_index(f"ix_day_passes_{name}", "day_passes", [name])
    op.create_table(
        "purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("guest_id", sa.String(64), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("product_key", sa.String(40), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("credits_granted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_checkout_session_id"),
        sa.UniqueConstraint("stripe_payment_intent_id"),
    )
    for name in ("user_id", "guest_id", "kind", "job_id", "status"):
        op.create_index(f"ix_purchases_{name}", "purchases", [name])
    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_stripe_events_event_type", "stripe_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_stripe_events_event_type", table_name="stripe_events")
    op.drop_table("stripe_events")
    for name in ("status", "job_id", "kind", "guest_id", "user_id"):
        op.drop_index(f"ix_purchases_{name}", table_name="purchases")
    op.drop_table("purchases")
    for name in ("ends_at", "starts_at", "guest_id", "user_id"):
        op.drop_index(f"ix_day_passes_{name}", table_name="day_passes")
    op.drop_table("day_passes")
    for name in (
        "current_period_end",
        "status",
        "stripe_customer_id",
        "stripe_subscription_id",
        "user_id",
    ):
        op.drop_index(f"ix_subscriptions_{name}", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_credit_ledger_reference_id", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_expires_at", table_name="credit_ledger")
    op.drop_column("credit_ledger", "note")
    op.drop_column("credit_ledger", "expires_at")
    op.drop_column("credit_ledger", "reference_id")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
