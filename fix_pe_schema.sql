-- Fix PE Schema - Create missing tables and fix references

-- Create pe_investor table if not exists
CREATE TABLE IF NOT EXISTS pe_investor (
    investor_id VARCHAR(36) PRIMARY KEY,
    investor_code VARCHAR(50) NOT NULL UNIQUE,
    investor_name VARCHAR(255) NOT NULL,
    investor_type VARCHAR(50),
    legal_entity_name VARCHAR(255),
    tax_id VARCHAR(50),
    domicile VARCHAR(100),
    contact_info JSON,
    metadata JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_investor_name ON pe_investor(investor_name);
CREATE INDEX IF NOT EXISTS idx_investor_type ON pe_investor(investor_type);

-- Create pe_document table if not exists (in case first migration didn't run)
CREATE TABLE IF NOT EXISTS pe_document (
    doc_id VARCHAR(36) PRIMARY KEY,
    fund_id VARCHAR(36),
    investor_id VARCHAR(36),
    doc_type VARCHAR(40) NOT NULL,
    period_end DATE,
    as_of DATE,
    doc_date DATE,
    file_hash VARCHAR(64) UNIQUE,
    path TEXT,
    mime VARCHAR(100),
    pages INTEGER,
    ocr_used BOOLEAN DEFAULT false,
    source_trace JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ensure all required tables exist before creating foreign key constraints
DO $$
BEGIN
    -- Check if all base tables exist
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_investor') AND
       EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_document') AND
       EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pe_fund_master') THEN
        RAISE NOTICE 'All base tables exist, foreign keys can be created';
    ELSE
        RAISE NOTICE 'Some base tables are missing, please run migrations in order';
    END IF;
END $$;

-- Add this to alembic_version if migrations were partially applied
-- INSERT INTO alembic_version (version_num) VALUES ('pe_enhanced_001') ON CONFLICT DO NOTHING;