"""add asset shopify fields

Revision ID: 0007_add_asset_shopify_fields
Revises: 0006_add_shopify_stores
Create Date: 2026-04-07 00:00:02.000007
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_asset_shopify_fields"
down_revision = "0006_add_shopify_stores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("shopify_product_id", sa.String(length=128), nullable=True))
    op.add_column("assets", sa.Column("shopify_media_id", sa.String(length=128), nullable=True))
    op.add_column("assets", sa.Column("shopify_publish_status", sa.String(length=32), nullable=True))
    op.add_column("assets", sa.Column("shopify_error_message", sa.Text(), nullable=True))
    op.add_column("assets", sa.Column("shopify_published_at", sa.DateTime(), nullable=True))
    op.create_index("ix_assets_shopify_publish_status", "assets", ["shopify_publish_status"])


def downgrade() -> None:
    op.drop_index("ix_assets_shopify_publish_status", table_name="assets")
    op.drop_column("assets", "shopify_published_at")
    op.drop_column("assets", "shopify_error_message")
    op.drop_column("assets", "shopify_publish_status")
    op.drop_column("assets", "shopify_media_id")
    op.drop_column("assets", "shopify_product_id")
