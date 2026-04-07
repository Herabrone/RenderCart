"""
Add approval status fields to assets table

Revision ID: 2024_04_07_add_approval_status_to_assets
Revises: 2024_01_01_initial_migration
Create Date: 2024-04-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2024_04_07_add_approval_status_to_assets'
down_revision = '2024_01_01_initial_migration'
branch_labels = None
depends_on = None


def upgrade():
    # Add approval_status column with default value 'pending'
    op.add_column('assets', 
                  sa.Column('approval_status', sa.String(length=32), nullable=False, server_default='pending'))
    
    # Add rejection_reason column
    op.add_column('assets', 
                  sa.Column('rejection_reason', sa.Text(), nullable=True))
    
    # Add approved_by column
    op.add_column('assets', 
                  sa.Column('approved_by', sa.String(length=64), nullable=True))
    
    # Add approved_at column
    op.add_column('assets', 
                  sa.Column('approved_at', sa.DateTime(), nullable=True))
    
    # Add rejected_by column
    op.add_column('assets', 
                  sa.Column('rejected_by', sa.String(length=64), nullable=True))
    
    # Add rejected_at column
    op.add_column('assets', 
                  sa.Column('rejected_at', sa.DateTime(), nullable=True))
    
    # Add index for approval_status for faster queries
    op.create_index(op.f('ix_assets_approval_status'), 'assets', ['approval_status'], unique=False)


def downgrade():
    # Remove index
    op.drop_index(op.f('ix_assets_approval_status'), table_name='assets')
    
    # Remove all columns in reverse order
    op.drop_column('assets', 'rejected_at')
    op.drop_column('assets', 'rejected_by')
    op.drop_column('assets', 'approved_at')
    op.drop_column('assets', 'approved_by')
    op.drop_column('assets', 'rejection_reason')
    op.drop_column('assets', 'approval_status')
