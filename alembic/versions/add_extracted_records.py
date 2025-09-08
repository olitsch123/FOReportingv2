"""Add extracted_records to document_tracker

Revision ID: add_extracted_records
Revises: add_document_tracker
Create Date: 2025-01-04 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_extracted_records'
down_revision = 'add_document_tracker'
branch_labels = None
depends_on = None


def upgrade():
    # Add extracted_records column to document_tracker table
    op.add_column('document_tracker', sa.Column('extracted_records', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    # Remove extracted_records column
    op.drop_column('document_tracker', 'extracted_records')