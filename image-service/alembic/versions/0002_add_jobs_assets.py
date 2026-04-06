"""add jobs and assets

Revision ID: 0002_add_jobs_assets
Revises: 0001_initial
Create Date: 2026-04-06 00:00:00.000001
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_jobs_assets'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('job_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('business_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('image_url', sa.String(length=2048), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('preset_id', sa.String(length=128), nullable=True),
        sa.Column('use_case', sa.String(length=64), nullable=True),
        sa.Column('product_category', sa.String(length=64), nullable=True),
        sa.Column('brand_style', sa.String(length=128), nullable=True),
        sa.Column('output_format', sa.String(length=64), nullable=True),
        sa.Column('mode', sa.String(length=64), nullable=True),
        sa.Column('num_outputs', sa.Integer(), nullable=True),
        sa.Column('callback_url', sa.String(length=2048), nullable=True),
        sa.Column('job_metadata', sa.JSON(), nullable=True),
        sa.Column('actual_model', sa.String(length=128), nullable=True),
        sa.Column('inference_config_used', sa.JSON(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('step', sa.String(length=128), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
    )
    op.create_index('ix_jobs_business_id', 'jobs', ['business_id'])
    op.create_index('ix_jobs_job_id', 'jobs', ['job_id'])

    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_type', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=True),
        sa.Column('asset_url', sa.String(length=2048), nullable=False),
        sa.Column('output_index', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_format', sa.String(length=32), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('asset_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_assets_job_id', 'assets', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_assets_job_id', table_name='assets')
    op.drop_table('assets')
    op.drop_index('ix_jobs_job_id', table_name='jobs')
    op.drop_index('ix_jobs_business_id', table_name='jobs')
    op.drop_table('jobs')
