"""Add reconciliation log table

Revision ID: add_reconciliation_log
Revises: add_embedding_columns
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_reconciliation_log'
down_revision = 'add_embedding_columns'
branch_labels = None
depends_on = None


def upgrade():
    """Create reconciliation log table."""
    op.create_table(
        'pe_reconciliation_log',
        sa.Column('reconciliation_id', sa.String(36), primary_key=True),
        sa.Column('fund_id', sa.String(100), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('findings_count', sa.Integer(), default=0),
        sa.Column('critical_count', sa.Integer(), default=0),
        sa.Column('results_json', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )
    
    # Create indexes for performance
    op.create_index('idx_pe_reconciliation_fund_date', 'pe_reconciliation_log', ['fund_id', 'as_of_date'])
    op.create_index('idx_pe_reconciliation_status', 'pe_reconciliation_log', ['status'])
    op.create_index('idx_pe_reconciliation_created', 'pe_reconciliation_log', ['created_at'])


def downgrade():
    """Drop reconciliation log table."""
    op.drop_index('idx_pe_reconciliation_created', 'pe_reconciliation_log')
    op.drop_index('idx_pe_reconciliation_status', 'pe_reconciliation_log')
    op.drop_index('idx_pe_reconciliation_fund_date', 'pe_reconciliation_log')
    op.drop_table('pe_reconciliation_log')