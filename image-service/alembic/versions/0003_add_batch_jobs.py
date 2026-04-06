"""add batch jobs and batch_id fields

Revision ID: 0003_add_batch_jobs
Revises: 0002_add_jobs_assets
Create Date: 2026-04-06 00:00:00.000003
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_batch_jobs'
down_revision = '0002_add_jobs_assets'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'batch_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('batch_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('business_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('total_items', sa.Integer(), nullable=False),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pending_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('preset_id', sa.String(length=128), nullable=True),
        sa.Column('use_case', sa.String(length=64), nullable=True),
        sa.Column('product_category', sa.String(length=64), nullable=True),
        sa.Column('brand_style', sa.String(length=128), nullable=True),
        sa.Column('output_format', sa.String(length=64), nullable=True),
        sa.Column('mode', sa.String(length=64), nullable=True),
        sa.Column('batch_error', sa.Text(), nullable=True),
    )
    op.create_index('ix_batch_jobs_batch_id', 'batch_jobs', ['batch_id'])

    op.add_column('jobs', sa.Column('batch_id', sa.String(length=128), nullable=True))
    op.add_column('jobs', sa.Column('item_index', sa.Integer(), nullable=True))
    op.add_column('jobs', sa.Column('item_label', sa.String(length=128), nullable=True))
    op.add_column('jobs', sa.Column('input_file_name', sa.String(length=256), nullable=True))
    op.add_column('jobs', sa.Column('original_image_url', sa.String(length=2048), nullable=True))
    op.create_index('ix_jobs_batch_id', 'jobs', ['batch_id'])


def downgrade() -> None:
    op.drop_index('ix_jobs_batch_id', table_name='jobs')
    op.drop_column('jobs', 'original_image_url')
    op.drop_column('jobs', 'input_file_name')
    op.drop_column('jobs', 'item_label')
    op.drop_column('jobs', 'item_index')
    op.drop_column('jobs', 'batch_id')
    op.drop_index('ix_batch_jobs_batch_id', table_name='batch_jobs')
    op.drop_table('batch_jobs')
