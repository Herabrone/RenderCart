"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'business_api_keys',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('business_id', sa.String(length=64), nullable=False, unique=True),
        sa.Column('api_key_hash', sa.String(length=256), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('business_api_keys')
    op.drop_table('workspaces')
