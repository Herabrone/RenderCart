"""Store dynamic QR targets, anonymous scan analytics, and abuse reports."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_dynamic_qr_codes"
down_revision: str | None = "0014_word_quota_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dynamic_qr_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scan_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_dynamic_qr_codes_user_id", "dynamic_qr_codes", ["user_id"])
    op.create_index("ix_dynamic_qr_owner_created", "dynamic_qr_codes", ["user_id", "created_at"])
    op.create_table(
        "dynamic_qr_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("qr_id", sa.Uuid(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("device_type", sa.String(length=16), nullable=False),
        sa.Column(
            "scanned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["qr_id"], ["dynamic_qr_codes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dynamic_qr_scans_qr_id", "dynamic_qr_scans", ["qr_id"])
    op.create_index("ix_dynamic_qr_scans_scanned_at", "dynamic_qr_scans", ["scanned_at"])
    op.create_index("ix_dynamic_qr_scans_code_time", "dynamic_qr_scans", ["qr_id", "scanned_at"])
    op.create_table(
        "dynamic_qr_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("qr_id", sa.Uuid(), nullable=True),
        sa.Column("qr_code", sa.String(length=32), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("message", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["qr_id"], ["dynamic_qr_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dynamic_qr_reports_qr_id", "dynamic_qr_reports", ["qr_id"])
    op.create_index("ix_dynamic_qr_reports_created", "dynamic_qr_reports", ["created_at"])


def downgrade() -> None:
    op.drop_table("dynamic_qr_reports")
    op.drop_table("dynamic_qr_scans")
    op.drop_table("dynamic_qr_codes")
