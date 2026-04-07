"""add shopify stores

Revision ID: 0006_add_shopify_stores
Revises: 0005_add_brand_kits
Create Date: 2026-04-07 00:00:01.000006
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_shopify_stores"
down_revision = "0005_add_brand_kits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shopify_stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.String(length=64), nullable=False),
        sa.Column("shop_domain", sa.String(length=256), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopify_stores_id", "shopify_stores", ["id"])
    op.create_index("ix_shopify_stores_business_id", "shopify_stores", ["business_id"])
    op.create_index("ix_shopify_stores_shop_domain", "shopify_stores", ["shop_domain"])
    op.create_index("ix_shopify_stores_status", "shopify_stores", ["status"])


def downgrade() -> None:
    op.drop_index("ix_shopify_stores_status", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_shop_domain", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_business_id", table_name="shopify_stores")
    op.drop_index("ix_shopify_stores_id", table_name="shopify_stores")
    op.drop_table("shopify_stores")
