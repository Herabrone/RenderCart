"""hardening schema updates

Revision ID: 0004_hardening_schema_updates
Revises: 0003_add_batch_jobs
Create Date: 2026-04-06 00:00:00.000004
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_hardening_schema_updates"
down_revision = "0003_add_batch_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    op.create_index("ix_assets_storage_key", "assets", ["storage_key"])
    op.create_index("ix_assets_created_at", "assets", ["created_at"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_batch_jobs_business_id", "batch_jobs", ["business_id"])
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"])
    op.create_index("ix_batch_jobs_created_at", "batch_jobs", ["created_at"])
    op.create_foreign_key(
        "fk_jobs_batch_id_batch_jobs",
        "jobs",
        "batch_jobs",
        ["batch_id"],
        ["batch_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_batch_id_batch_jobs", "jobs", type_="foreignkey")
    op.drop_index("ix_batch_jobs_created_at", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_status", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_business_id", table_name="batch_jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_assets_created_at", table_name="assets")
    op.drop_index("ix_assets_storage_key", table_name="assets")
    op.drop_column("assets", "storage_key")
