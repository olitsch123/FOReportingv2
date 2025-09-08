#!/usr/bin/env python3
"""Check what documents have been processed and stored."""

import os
os.environ["DEPLOYMENT_MODE"] = "local"
os.environ["PYTHONPATH"] = "."

from dotenv import load_dotenv
load_dotenv()

from app.database.connection import get_engine
from sqlalchemy import text
import pandas as pd

def check_documents():
    """Check processed documents in database."""
    print("=" * 60)
    print("Checking Processed Documents")
    print("=" * 60)
    
    engine = get_engine()
    
    # Check documents table
    print("\n1. Documents table:")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM documents"))
            count = result.scalar()
            print(f"   Total documents: {count}")
            
            if count > 0:
                # Show recent documents
                query = """
                SELECT 
                    id,
                    file_name,
                    document_type,
                    investor_code,
                    created_at,
                    file_size
                FROM documents
                ORDER BY created_at DESC
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent documents:")
                for _, row in df.iterrows():
                    print(f"   - {row['file_name'][:50]}... ({row['document_type']}) - {row['created_at']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check PE documents
    print("\n2. PE Documents table:")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_document"))
            count = result.scalar()
            print(f"   Total PE documents: {count}")
            
            if count > 0:
                query = """
                SELECT 
                    id,
                    file_name,
                    doc_type,
                    upload_date,
                    fund_name
                FROM pe_document
                ORDER BY upload_date DESC
                LIMIT 10
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent PE documents:")
                for _, row in df.iterrows():
                    print(f"   - {row['file_name'][:50]}... ({row['doc_type']}) - Fund: {row['fund_name']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check capital accounts
    print("\n3. Capital Accounts:")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM pe_capital_account"))
            count = result.scalar()
            print(f"   Total capital account entries: {count}")
            
            if count > 0:
                query = """
                SELECT 
                    fund_name,
                    investor_name,
                    period_date,
                    ending_balance
                FROM pe_capital_account
                ORDER BY period_date DESC
                LIMIT 5
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent entries:")
                for _, row in df.iterrows():
                    print(f"   - {row['fund_name']} / {row['investor_name']} - {row['period_date']}: ${row['ending_balance']:,.2f}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Check extraction audit
    print("\n4. Processing Activity:")
    try:
        with engine.connect() as conn:
            # Check ingestion jobs
            result = conn.execute(text("SELECT COUNT(*) FROM ingestion_job"))
            job_count = result.scalar()
            print(f"   Ingestion jobs: {job_count}")
            
            # Check files
            result = conn.execute(text("SELECT COUNT(*) FROM ingestion_file"))
            file_count = result.scalar()
            print(f"   Ingestion files: {file_count}")
            
            if file_count > 0:
                query = """
                SELECT 
                    file_name,
                    status,
                    created_at,
                    updated_at
                FROM ingestion_file
                ORDER BY created_at DESC
                LIMIT 5
                """
                df = pd.read_sql(query, conn)
                print("\n   Recent file processing:")
                for _, row in df.iterrows():
                    print(f"   - {row['file_name'][:40]}... - Status: {row['status']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_documents()