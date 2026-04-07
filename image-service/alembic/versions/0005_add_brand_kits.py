"""add brand kits

Revision ID: 0005_add_brand_kits
Revises: 0004_hardening_schema_updates
Create Date: 2026-04-06 00:00:01.000005
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_brand_kits"
down_revision = "0004_hardening_schema_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jobs", "brand_style", existing_type=sa.String(length=128), type_=sa.Text())
    op.alter_column(
        "batch_jobs",
        "brand_style",
        existing_type=sa.String(length=128),
        type_=sa.Text(),
    )

    op.create_table(
        "brand_kits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("background", sa.String(length=256), nullable=False),
        sa.Column("lighting", sa.String(length=256), nullable=False),
        sa.Column("tone", sa.String(length=256), nullable=False),
        sa.Column("framing", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brand_kits_id", "brand_kits", ["id"])
    op.create_index("ix_brand_kits_business_id", "brand_kits", ["business_id"])
    op.create_index("ix_brand_kits_created_at", "brand_kits", ["created_at"])

    op.add_column("jobs", sa.Column("brand_kit_id", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("brand_kit_snapshot", sa.JSON(), nullable=True))
    op.create_index("ix_jobs_brand_kit_id", "jobs", ["brand_kit_id"])

    op.add_column("batch_jobs", sa.Column("brand_kit_id", sa.Integer(), nullable=True))
    op.add_column("batch_jobs", sa.Column("brand_kit_snapshot", sa.JSON(), nullable=True))
    op.create_index("ix_batch_jobs_brand_kit_id", "batch_jobs", ["brand_kit_id"])


def downgrade() -> None:
    op.drop_index("ix_batch_jobs_brand_kit_id", table_name="batch_jobs")
    op.drop_column("batch_jobs", "brand_kit_snapshot")
    op.drop_column("batch_jobs", "brand_kit_id")

    op.drop_index("ix_jobs_brand_kit_id", table_name="jobs")
    op.drop_column("jobs", "brand_kit_snapshot")
    op.drop_column("jobs", "brand_kit_id")

    op.drop_index("ix_brand_kits_created_at", table_name="brand_kits")
    op.drop_index("ix_brand_kits_business_id", table_name="brand_kits")
    op.drop_index("ix_brand_kits_id", table_name="brand_kits")
    op.drop_table("brand_kits")

    op.alter_column(
        "batch_jobs",
        "brand_style",
        existing_type=sa.Text(),
        type_=sa.String(length=128),
    )
    op.alter_column("jobs", "brand_style", existing_type=sa.Text(), type_=sa.String(length=128))
