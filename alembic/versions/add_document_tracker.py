"""Add document tracker table

Revision ID: add_document_tracker
Revises: pe_enhanced_001
Create Date: 2025-09-04 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_document_tracker'
down_revision = 'pe_enhanced_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create document_tracker table
    op.create_table('document_tracker',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_name', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.Column('last_processed', sa.DateTime(), nullable=True),
        sa.Column('processing_count', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.String(length=100), nullable=True),
        sa.Column('fund_name', sa.String(length=200), nullable=True),
        sa.Column('investor_name', sa.String(length=200), nullable=True),
        sa.Column('period_date', sa.DateTime(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('pe_document_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_path', 'file_hash', name='uq_path_hash')
    )
    
    # Create indexes
    op.create_index(op.f('ix_document_tracker_file_hash'), 'document_tracker', ['file_hash'], unique=True)
    op.create_index(op.f('ix_document_tracker_status'), 'document_tracker', ['status'], unique=False)
    op.create_index(op.f('ix_document_tracker_first_seen'), 'document_tracker', ['first_seen'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_document_tracker_first_seen'), table_name='document_tracker')
    op.drop_index(op.f('ix_document_tracker_status'), table_name='document_tracker')
    op.drop_index(op.f('ix_document_tracker_file_hash'), table_name='document_tracker')
    
    # Drop table
    op.drop_table('document_tracker')