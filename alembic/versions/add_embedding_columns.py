"""Add embedding columns to pe_document

Revision ID: add_embedding_columns
Revises: add_extracted_records
Create Date: 2025-01-04 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_embedding_columns'
down_revision = 'add_extracted_records'
branch_labels = None
depends_on = None


def upgrade():
    # Add embedding-related columns to pe_document table
    op.add_column('pe_document', sa.Column('embedding_status', sa.String(50), nullable=True))
    op.add_column('pe_document', sa.Column('chunk_count', sa.Integer(), nullable=True))
    op.add_column('pe_document', sa.Column('embedding_error', sa.Text(), nullable=True))


def downgrade():
    # Remove embedding-related columns
    op.drop_column('pe_document', 'embedding_error')
    op.drop_column('pe_document', 'chunk_count')
    op.drop_column('pe_document', 'embedding_status')