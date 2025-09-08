"""PE enhanced schema for production-grade data extraction

Revision ID: pe_enhanced_001
Revises: e01e58ef9cbe
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'pe_enhanced_001'
down_revision = 'e01e58ef9cbe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pe_investor table (must be created before tables that reference it)
    op.create_table('pe_investor',
        sa.Column('investor_id', sa.String(36), nullable=False),
        sa.Column('investor_code', sa.String(50), nullable=False),
        sa.Column('investor_name', sa.String(255), nullable=False),
        sa.Column('investor_type', sa.String(50)),
        sa.Column('legal_entity_name', sa.String(255)),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('domicile', sa.String(100)),
        sa.Column('contact_info', sa.JSON()),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('investor_id'),
        sa.UniqueConstraint('investor_code')
    )
    op.create_index('idx_investor_name', 'pe_investor', ['investor_name'])
    op.create_index('idx_investor_type', 'pe_investor', ['investor_type'])
    
    # Create pe_fund_master table
    op.create_table('pe_fund_master',
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_code', sa.String(50), nullable=False),
        sa.Column('fund_name', sa.String(255), nullable=False),
        sa.Column('fund_manager', sa.String(255)),
        sa.Column('management_company', sa.String(255)),
        sa.Column('general_partner', sa.String(255)),
        sa.Column('vintage_year', sa.Integer()),
        sa.Column('fund_size', sa.Numeric(20, 2)),
        sa.Column('target_size', sa.Numeric(20, 2)),
        sa.Column('currency', sa.String(3)),
        sa.Column('fund_type', sa.String(50)),
        sa.Column('investment_strategy', sa.Text()),
        sa.Column('legal_structure', sa.String(100)),
        sa.Column('domicile', sa.String(100)),
        sa.Column('inception_date', sa.Date()),
        sa.Column('first_close_date', sa.Date()),
        sa.Column('final_close_date', sa.Date()),
        sa.Column('term_years', sa.Integer()),
        sa.Column('extension_years', sa.Integer()),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('fund_id'),
        sa.UniqueConstraint('fund_code')
    )
    op.create_index('idx_fund_master_name', 'pe_fund_master', ['fund_name'])
    op.create_index('idx_fund_master_vintage', 'pe_fund_master', ['vintage_year'])
    
    # Create pe_share_class table
    op.create_table('pe_share_class',
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('class_code', sa.String(20)),
        sa.Column('class_name', sa.String(100)),
        sa.Column('currency', sa.String(3)),
        sa.Column('management_fee_pct', sa.Numeric(5, 3)),
        sa.Column('carried_interest_pct', sa.Numeric(5, 3)),
        sa.Column('preferred_return_pct', sa.Numeric(5, 3)),
        sa.Column('hurdle_rate', sa.Numeric(5, 3)),
        sa.Column('catch_up_pct', sa.Numeric(5, 3)),
        sa.Column('fee_terms', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['fund_id'], ['pe_fund_master.fund_id'], ),
        sa.PrimaryKeyConstraint('class_id')
    )
    
    # Create pe_commitment_enhanced table (replaces pe_commitment)
    op.create_table('pe_commitment_enhanced',
        sa.Column('commitment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('investor_id', sa.String(36), nullable=False),
        sa.Column('share_class_id', postgresql.UUID(as_uuid=True)),
        sa.Column('commitment_amount', sa.Numeric(20, 2), nullable=False),
        sa.Column('commitment_date', sa.Date(), nullable=False),
        sa.Column('currency', sa.String(3)),
        sa.Column('side_letter', sa.Boolean(), default=False),
        sa.Column('advisory_committee', sa.Boolean(), default=False),
        sa.Column('key_person', sa.Boolean(), default=False),
        sa.Column('excuse_rights', sa.JSON()),
        sa.Column('special_terms', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.ForeignKeyConstraint(['fund_id'], ['pe_fund_master.fund_id'], ),
        sa.ForeignKeyConstraint(['investor_id'], ['pe_investor.investor_id'], ),
        sa.ForeignKeyConstraint(['share_class_id'], ['pe_share_class.class_id'], ),
        sa.PrimaryKeyConstraint('commitment_id'),
        sa.UniqueConstraint('fund_id', 'investor_id', name='uq_fund_investor_commitment')
    )
    
    # Create pe_capital_account table (most critical)
    op.create_table('pe_capital_account',
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('investor_id', sa.String(36), nullable=False),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(20)),  # QUARTERLY, ANNUAL, MONTHLY
        sa.Column('period_label', sa.String(20)),  # Q4 2023, FY 2023
        
        # Balances
        sa.Column('beginning_balance', sa.Numeric(20, 2)),
        sa.Column('ending_balance', sa.Numeric(20, 2)),
        sa.Column('beginning_balance_local', sa.Numeric(20, 2)),
        sa.Column('ending_balance_local', sa.Numeric(20, 2)),
        
        # Activity - Contributions
        sa.Column('contributions_period', sa.Numeric(20, 2)),
        sa.Column('contributions_itd', sa.Numeric(20, 2)),
        
        # Activity - Distributions
        sa.Column('distributions_period', sa.Numeric(20, 2)),
        sa.Column('distributions_itd', sa.Numeric(20, 2)),
        sa.Column('distributions_roc_period', sa.Numeric(20, 2)),  # Return of Capital
        sa.Column('distributions_gain_period', sa.Numeric(20, 2)),  # Realized Gains
        sa.Column('distributions_income_period', sa.Numeric(20, 2)),  # Income
        sa.Column('distributions_tax_period', sa.Numeric(20, 2)),  # Tax
        sa.Column('distributions_roc_itd', sa.Numeric(20, 2)),
        sa.Column('distributions_gain_itd', sa.Numeric(20, 2)),
        sa.Column('distributions_income_itd', sa.Numeric(20, 2)),
        sa.Column('distributions_tax_itd', sa.Numeric(20, 2)),
        
        # Fees & Expenses
        sa.Column('management_fees_period', sa.Numeric(20, 2)),
        sa.Column('management_fees_itd', sa.Numeric(20, 2)),
        sa.Column('partnership_expenses_period', sa.Numeric(20, 2)),
        sa.Column('partnership_expenses_itd', sa.Numeric(20, 2)),
        sa.Column('organizational_expenses_period', sa.Numeric(20, 2)),
        sa.Column('organizational_expenses_itd', sa.Numeric(20, 2)),
        
        # Gains/Losses
        sa.Column('realized_gain_loss_period', sa.Numeric(20, 2)),
        sa.Column('realized_gain_loss_itd', sa.Numeric(20, 2)),
        sa.Column('unrealized_gain_loss_period', sa.Numeric(20, 2)),
        sa.Column('unrealized_gain_loss_itd', sa.Numeric(20, 2)),
        
        # Commitments
        sa.Column('total_commitment', sa.Numeric(20, 2)),
        sa.Column('drawn_commitment', sa.Numeric(20, 2)),
        sa.Column('unfunded_commitment', sa.Numeric(20, 2)),
        sa.Column('recallable_distributions', sa.Numeric(20, 2)),
        sa.Column('remaining_commitment', sa.Numeric(20, 2)),
        
        # Share/Ownership info
        sa.Column('ownership_pct', sa.Numeric(10, 6)),
        sa.Column('shares_owned', sa.Numeric(20, 6)),
        
        # Currency info
        sa.Column('reporting_currency', sa.String(3)),
        sa.Column('local_currency', sa.String(3)),
        sa.Column('fx_rate', sa.Numeric(12, 6)),
        
        # Metadata
        sa.Column('source_doc_id', sa.String(36)),
        sa.Column('extraction_confidence', sa.Numeric(3, 2)),
        sa.Column('validated', sa.Boolean(), default=False),
        sa.Column('validation_notes', sa.Text()),
        sa.Column('manual_adjustments', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        
        sa.ForeignKeyConstraint(['fund_id'], ['pe_fund_master.fund_id'], ),
        sa.ForeignKeyConstraint(['investor_id'], ['pe_investor.investor_id'], ),
        sa.ForeignKeyConstraint(['source_doc_id'], ['pe_document.doc_id'], ),
        sa.PrimaryKeyConstraint('account_id'),
        sa.UniqueConstraint('fund_id', 'investor_id', 'as_of_date', name='uq_capital_account')
    )
    
    # Create comprehensive indexes for capital account queries
    op.create_index('idx_capital_account_time', 'pe_capital_account', ['fund_id', 'investor_id', 'as_of_date'])
    op.create_index('idx_capital_account_period', 'pe_capital_account', ['fund_id', 'period_type', 'as_of_date'])
    op.create_index('idx_capital_account_validation', 'pe_capital_account', ['validated', 'extraction_confidence'])
    
    # Create pe_performance_metrics table
    op.create_table('pe_performance_metrics',
        sa.Column('metric_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('investor_id', sa.String(36)),
        sa.Column('as_of_date', sa.Date(), nullable=False),
        sa.Column('calculation_type', sa.String(20)),  # REPORTED, CALCULATED
        
        # IRR Metrics
        sa.Column('irr_gross', sa.Numeric(8, 5)),
        sa.Column('irr_net', sa.Numeric(8, 5)),
        sa.Column('irr_gross_local', sa.Numeric(8, 5)),
        sa.Column('irr_net_local', sa.Numeric(8, 5)),
        
        # Multiple Metrics
        sa.Column('moic_gross', sa.Numeric(8, 4)),
        sa.Column('moic_net', sa.Numeric(8, 4)),
        sa.Column('tvpi', sa.Numeric(8, 4)),
        sa.Column('dpi', sa.Numeric(8, 4)),
        sa.Column('rvpi', sa.Numeric(8, 4)),
        sa.Column('pic', sa.Numeric(8, 4)),  # Paid-in Capital ratio
        
        # Quartile Rankings
        sa.Column('irr_quartile', sa.Integer()),
        sa.Column('moic_quartile', sa.Integer()),
        
        # Metadata
        sa.Column('source_doc_id', sa.String(36)),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        
        sa.ForeignKeyConstraint(['fund_id'], ['pe_fund_master.fund_id'], ),
        sa.ForeignKeyConstraint(['investor_id'], ['pe_investor.investor_id'], ),
        sa.ForeignKeyConstraint(['source_doc_id'], ['pe_document.doc_id'], ),
        sa.PrimaryKeyConstraint('metric_id'),
        sa.UniqueConstraint('fund_id', 'investor_id', 'as_of_date', name='uq_performance_metrics')
    )
    
    # Create extraction_audit table
    op.create_table('extraction_audit',
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doc_id', sa.String(36), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('extracted_value', sa.Text()),
        sa.Column('extraction_method', sa.String(50)),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('validation_status', sa.String(20)),
        sa.Column('validation_errors', sa.JSON()),
        sa.Column('manual_override', sa.Text()),
        sa.Column('override_reason', sa.Text()),
        sa.Column('reviewer_id', sa.String(100)),
        sa.Column('extraction_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('review_timestamp', sa.DateTime(timezone=True)),
        
        sa.ForeignKeyConstraint(['doc_id'], ['pe_document.doc_id'], ),
        sa.PrimaryKeyConstraint('audit_id')
    )
    op.create_index('idx_extraction_audit_doc', 'extraction_audit', ['doc_id', 'field_name'])
    op.create_index('idx_extraction_audit_confidence', 'extraction_audit', ['confidence_score', 'validation_status'])
    
    # Create reconciliation_log table
    op.create_table('reconciliation_log',
        sa.Column('reconciliation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('doc_id', sa.String(36), nullable=False),
        sa.Column('reconciliation_type', sa.String(50)),  # BALANCE, COMMITMENT, PERFORMANCE
        sa.Column('status', sa.String(20)),  # PASS, FAIL, REVIEW
        sa.Column('differences', sa.JSON()),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('requires_review', sa.Boolean(), default=False),
        sa.Column('reviewed', sa.Boolean(), default=False),
        sa.Column('reviewer_notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        
        sa.ForeignKeyConstraint(['doc_id'], ['pe_document.doc_id'], ),
        sa.PrimaryKeyConstraint('reconciliation_id')
    )
    op.create_index('idx_reconciliation_status', 'reconciliation_log', ['status', 'requires_review'])
    
    # Create pe_portfolio_company table
    op.create_table('pe_portfolio_company',
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fund_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('industry', sa.String(100)),
        sa.Column('sector', sa.String(100)),
        sa.Column('geography', sa.String(100)),
        sa.Column('investment_date', sa.Date()),
        sa.Column('exit_date', sa.Date()),
        sa.Column('status', sa.String(50)),  # ACTIVE, EXITED, WRITTEN_OFF
        sa.Column('cost_basis', sa.Numeric(20, 2)),
        sa.Column('realized_proceeds', sa.Numeric(20, 2)),
        sa.Column('unrealized_value', sa.Numeric(20, 2)),
        sa.Column('ownership_pct', sa.Numeric(10, 6)),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        
        sa.ForeignKeyConstraint(['fund_id'], ['pe_fund_master.fund_id'], ),
        sa.PrimaryKeyConstraint('company_id')
    )
    op.create_index('idx_portfolio_company_fund', 'pe_portfolio_company', ['fund_id', 'status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('pe_portfolio_company')
    op.drop_table('reconciliation_log')
    op.drop_table('extraction_audit')
    op.drop_table('pe_performance_metrics')
    op.drop_table('pe_capital_account')
    op.drop_table('pe_commitment_enhanced')
    op.drop_table('pe_share_class')
    op.drop_table('pe_fund_master')