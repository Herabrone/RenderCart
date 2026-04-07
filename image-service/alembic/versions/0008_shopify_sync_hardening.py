"""Mark stores as disconnected when token is revoked (adds updated_at index).

Revision ID: 0008_shopify_sync_hardening
Revises: 0007_add_asset_shopify_fields
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0008_shopify_sync_hardening"
down_revision = "0007_add_asset_shopify_fields"
branch_labels = None
depends_on = None


def upgrade():
    # Index for efficient store lookups by status (used in edge-case handling).
    op.create_index(
        "ix_shopify_stores_status",
        "shopify_stores",
        ["status"],
        unique=False,
        if_not_exists=True,
    )

    # Track the publish_batch_id so bulk publishes can be grouped and queried.
    op.add_column(
        "assets",
        sa.Column("shopify_publish_batch_id", sa.String(64), nullable=True),
    )


def downgrade():
    op.drop_column("assets", "shopify_publish_batch_id")
    op.drop_index("ix_shopify_stores_status", table_name="shopify_stores")
