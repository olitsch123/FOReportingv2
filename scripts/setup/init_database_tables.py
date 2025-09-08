#!/usr/bin/env python3
"""Initialize database tables for FOReporting v2."""

import os
import subprocess
import sys
from pathlib import Path


def init_database():
    """Initialize database with all required tables."""
    print("=" * 60)
    print("Initializing FOReporting v2 Database")
    print("=" * 60)
    
    # Set environment for local mode
    os.environ["DEPLOYMENT_MODE"] = "local"
    os.environ["PYTHONPATH"] = "."
    
    # Check .env file
    if not Path(".env").exists():
        print("❌ .env file not found!")
        return False
    
    print("\n1. Loading environment...")
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set in .env!")
        return False
    
    print(f"   Database URL: {db_url.split('@')[1] if '@' in db_url else db_url}")
    
    # Run Alembic migrations
    print("\n2. Running database migrations...")
    try:
        # First check current state
        print("   Checking current migration state...")
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            env={**os.environ}
        )
        print(f"   Current state: {result.stdout.strip() if result.stdout else 'No migrations'}")
        
        # Run migrations
        print("\n   Applying all migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env={**os.environ}
        )
        
        if result.returncode == 0:
            print("   ✓ Migrations completed successfully!")
            print(f"   Output: {result.stdout.strip()}")
        else:
            print("   ❌ Migration failed!")
            print(f"   Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error running migrations: {e}")
        return False
    
    # Verify tables were created
    print("\n3. Verifying database tables...")
    try:
        from sqlalchemy import inspect, text

        from app.database.connection import get_engine
        
        engine = get_engine()
        inspector = inspect(engine)
        
        # Get all tables
        tables = inspector.get_table_names()
        
        if tables:
            print(f"   ✓ Found {len(tables)} tables:")
            for table in sorted(tables):
                # Get row count
                with engine.connect() as conn:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        print(f"     - {table}: {count} rows")
                    except:
                        print(f"     - {table}")
        else:
            print("   ❌ No tables found in database!")
            return False
            
    except Exception as e:
        print(f"   ❌ Error checking tables: {e}")
        return False
    
    # Check PE-specific tables
    print("\n4. Checking PE-specific tables...")
    required_tables = [
        'pe_fund',
        'pe_investor', 
        'pe_document',
        'pe_capital_account',
        'pe_nav_observation',
        'pe_cashflow',
        'pe_commitment',
        'pe_performance',
        'pe_extraction_audit',
        'documents',
        'document_chunks'
    ]
    
    missing_tables = [t for t in required_tables if t not in tables]
    if missing_tables:
        print(f"   ⚠️  Missing tables: {', '.join(missing_tables)}")
    else:
        print("   ✓ All required tables present!")
    
    print("\n" + "=" * 60)
    print("Database initialization complete!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)