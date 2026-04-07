"""Add users table for email/password authentication.

Revision ID: 0009_add_users
Revises: 0008_shopify_sync_hardening
Create Date: 2026-04-07

"""
from alembic import op
import sqlalchemy as sa

revision = "0009_add_users"
down_revision = "0008_shopify_sync_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("users")
