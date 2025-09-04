"""pe core schema

Revision ID: e01e58ef9cbe
Revises: 
Create Date: 2025-09-02 23:51:40.560837

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e01e58ef9cbe'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("dim_date",
        sa.Column("date_id", sa.Integer, primary_key=True),
        sa.Column("d", sa.Date, nullable=False, unique=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("day", sa.Integer, nullable=False),
        sa.Column("quarter", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
    )
    op.create_table("dim_period",
        sa.Column("period_id", sa.Integer, primary_key=True),
        sa.Column("period_date", sa.Date, nullable=False, unique=True),
        sa.Column("month", sa.SmallInteger, nullable=False),
        sa.Column("quarter", sa.SmallInteger, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
    )

    op.create_table("pe_document",
        sa.Column("doc_id", sa.String(36), primary_key=True),
        sa.Column("fund_id", sa.String(36)),
        sa.Column("investor_id", sa.String(36)),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("period_end", sa.Date),
        sa.Column("as_of", sa.Date),
        sa.Column("doc_date", sa.Date),
        sa.Column("file_hash", sa.String(64), unique=True),
        sa.Column("path", sa.Text),
        sa.Column("mime", sa.String(100)),
        sa.Column("pages", sa.Integer),
        sa.Column("ocr_used", sa.Boolean, server_default=sa.text("false")),
        sa.Column("source_trace", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table("pe_doc_page",
        sa.Column("doc_id", sa.String(36), nullable=False),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("text_hash", sa.Text),
        sa.Column("table_json", sa.JSON),
        sa.Column("bbox", sa.JSON),
        sa.Column("ocr_conf", sa.Numeric(5,4)),
        sa.PrimaryKeyConstraint("doc_id","page_no"),
    )

    op.create_table("pe_cashflow",
        sa.Column("cf_id", sa.Integer, primary_key=True),
        sa.Column("fund_id", sa.String(36), nullable=False),
        sa.Column("investor_id", sa.String(36), nullable=False),
        sa.Column("flow_date", sa.Date, nullable=False),
        sa.Column("flow_type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(24,8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fx_rate", sa.Numeric(18,8)),
        sa.Column("doc_id", sa.String(36)),
        sa.Column("line_ref", sa.Text),
        sa.Column("source_trace", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_cf_key","pe_cashflow",["fund_id","investor_id","flow_date","flow_type"])

    op.create_table("pe_nav_observation",
        sa.Column("nav_obs_id", sa.Integer, primary_key=True),
        sa.Column("fund_id", sa.String(36), nullable=False),
        sa.Column("investor_id", sa.String(36)),
        sa.Column("scope", sa.String(24), nullable=False, server_default="FUND"),
        sa.Column("nav_value", sa.Numeric(24,8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column("statement_date", sa.Date),
        sa.Column("coverage_start", sa.Date),
        sa.Column("coverage_end", sa.Date),
        sa.Column("period_id", sa.Integer, sa.ForeignKey("dim_period.period_id")),
        sa.Column("scenario", sa.String(16), nullable=False, server_default="AS_REPORTED"),
        sa.Column("version_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("restates_nav_obs_id", sa.Integer),
        sa.Column("doc_id", sa.String(36)),
        sa.Column("source_trace", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_navobs_fi_date","pe_nav_observation",["fund_id","investor_id","as_of_date"])
    op.create_index("idx_navobs_period","pe_nav_observation",["fund_id","investor_id","period_id"])

    op.create_table("ingestion_file",
        sa.Column("file_id", sa.Integer, primary_key=True),
        sa.Column("org_code", sa.Text),
        sa.Column("investor_code", sa.Text),
        sa.Column("source_system", sa.Text),
        sa.Column("source_uri", sa.Text),
        sa.Column("file_name", sa.Text),
        sa.Column("file_hash", sa.String(64), unique=True),
        sa.Column("received_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata", sa.JSON),
    )
    op.create_table("ingestion_job",
        sa.Column("job_id", sa.Integer, primary_key=True),
        sa.Column("file_id", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED"),
        sa.Column("pipeline", sa.JSON),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("error_message", sa.Text),
        sa.Column("logs", sa.JSON, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    for t in ["ingestion_job","ingestion_file","pe_nav_observation","pe_cashflow","pe_doc_page","pe_document","dim_period","dim_date"]:
        op.drop_table(t)
