#!/usr/bin/env python3
"""Check what data was actually extracted from processed documents."""

import os
os.environ["DEPLOYMENT_MODE"] = "local"
os.environ["PYTHONPATH"] = "."

from dotenv import load_dotenv
load_dotenv()

from app.database.connection import get_engine
from sqlalchemy import text
import pandas as pd

def check_extracted_data():
    """Check extracted data in various PE tables."""
    print("=" * 60)
    print("Checking Extracted Data from Document Processing")
    print("=" * 60)
    
    engine = get_engine()
    
    # 1. Check PE Funds
    print("\n1. PE Funds (pe_fund_master):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_fund_master"))
            count = result.scalar()
            print(f"   Total funds: {count}")
            
            if count > 0:
                query = """
                SELECT id, fund_name, fund_type, currency, vintage_year, created_at
                FROM pe_fund_master
                ORDER BY created_at DESC
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent funds:")
                for _, row in df.iterrows():
                    print(f"   - {row['fund_name']} ({row['fund_type']}) - {row['vintage_year']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 2. Check PE Investors
    print("\n2. PE Investors (pe_investor):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_investor"))
            count = result.scalar()
            print(f"   Total investors: {count}")
            
            if count > 0:
                query = """
                SELECT id, investor_name, investor_type, created_at
                FROM pe_investor
                ORDER BY created_at DESC
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent investors:")
                for _, row in df.iterrows():
                    print(f"   - {row['investor_name']} ({row['investor_type']})")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 3. Check Capital Accounts
    print("\n3. Capital Accounts (pe_capital_account):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_capital_account"))
            count = result.scalar()
            print(f"   Total capital account records: {count}")
            
            if count > 0:
                query = """
                SELECT 
                    fund_name,
                    investor_name,
                    period_date,
                    ending_balance,
                    commitment_amount,
                    created_at
                FROM pe_capital_account
                ORDER BY created_at DESC
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent capital account entries:")
                for _, row in df.iterrows():
                    fund = row['fund_name'] or 'Unknown Fund'
                    investor = row['investor_name'] or 'Unknown Investor'
                    balance = row['ending_balance'] if row['ending_balance'] else 0
                    print(f"   - {fund} / {investor} - {row['period_date']}: ${balance:,.2f}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 4. Check NAV Observations
    print("\n4. NAV Observations (pe_nav_observation):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_nav_observation"))
            count = result.scalar()
            print(f"   Total NAV observations: {count}")
            
            if count > 0:
                query = """
                SELECT 
                    fund_name,
                    observation_date,
                    nav_amount,
                    currency
                FROM pe_nav_observation
                ORDER BY created_at DESC
                LIMIT 5
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent NAV observations:")
                for _, row in df.iterrows():
                    fund = row['fund_name'] or 'Unknown Fund'
                    nav = row['nav_amount'] if row['nav_amount'] else 0
                    print(f"   - {fund} - {row['observation_date']}: {row['currency']} {nav:,.2f}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 5. Check Documents with Missing Fund/Investor Links
    print("\n5. Document Tracker - Missing Connections:")
    try:
        with engine.connect() as conn:
            # Documents without fund names
            query = """
            SELECT COUNT(*) as count
            FROM document_tracker
            WHERE status = 'completed' 
            AND (fund_name IS NULL OR fund_name = '')
            """
            result = conn.execute(text(query))
            no_fund = result.scalar()
            
            # Documents without investor names
            query = """
            SELECT COUNT(*) as count
            FROM document_tracker
            WHERE status = 'completed'
            AND (investor_name IS NULL OR investor_name = '')
            """
            result = conn.execute(text(query))
            no_investor = result.scalar()
            
            print(f"   Completed documents without fund name: {no_fund}")
            print(f"   Completed documents without investor name: {no_investor}")
            
            # Show examples of documents with missing info
            if no_fund > 0 or no_investor > 0:
                query = """
                SELECT 
                    file_name,
                    fund_name,
                    investor_name,
                    document_type
                FROM document_tracker
                WHERE status = 'completed'
                AND (fund_name IS NULL OR fund_name = '' 
                     OR investor_name IS NULL OR investor_name = '')
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Examples of documents with missing connections:")
                for _, row in df.iterrows():
                    fund = row['fund_name'] or '[MISSING FUND]'
                    investor = row['investor_name'] or '[MISSING INVESTOR]'
                    doc_type = row['document_type'] or '[UNKNOWN TYPE]'
                    print(f"   - {row['file_name'][:50]}...")
                    print(f"     Fund: {fund}, Investor: {investor}, Type: {doc_type}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 6. Check Performance Metrics
    print("\n6. Performance Metrics (pe_performance_metrics):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_performance_metrics"))
            count = result.scalar()
            print(f"   Total performance records: {count}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 7. Check Commitments
    print("\n7. Commitments (pe_commitment_enhanced):")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_commitment_enhanced"))
            count = result.scalar()
            print(f"   Total commitment records: {count}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)

if __name__ == "__main__":
    check_extracted_data()