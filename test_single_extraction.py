#!/usr/bin/env python3
"""Test extraction on a single document to see what's happening."""

import os
os.environ["DEPLOYMENT_MODE"] = "local"
os.environ["PYTHONPATH"] = "."

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from app.database.connection import get_db
from app.pe_docs.api import handle_file as pe_handle_file
import asyncio

async def test_single_file():
    """Test processing a single file."""
    # Find a capital account statement
    investor_path = Path(os.getenv("INVESTOR1_PATH"))
    
    # Look for a CAS file
    cas_files = list(investor_path.rglob("*CAS*.xlsx"))
    
    if not cas_files:
        print("No CAS files found!")
        return
    
    test_file = cas_files[0]
    print(f"Testing file: {test_file.name}")
    print(f"Full path: {test_file}")
    print("=" * 60)
    
    # Process the file
    db = next(get_db())
    try:
        print("Processing file...")
        result = await pe_handle_file(str(test_file), "default", "brainweb", db)
        
        if result:
            print(f"\nResult type: {type(result)}")
            print(f"Result: {result}")
            
            # Check if it's a PE document
            if hasattr(result, 'id'):
                print(f"\nPE Document created:")
                print(f"  ID: {result.id}")
                print(f"  Fund: {getattr(result, 'fund_name', 'Not extracted')}")
                print(f"  Type: {getattr(result, 'doc_type', 'Not extracted')}")
                
                # Check if capital accounts were extracted
                from sqlalchemy import text
                query = text("""
                    SELECT COUNT(*) FROM pe_capital_account 
                    WHERE document_id = :doc_id
                """)
                count = db.execute(query, {"doc_id": result.id}).scalar()
                print(f"\nCapital account records created: {count}")
        else:
            print("No result returned!")
            
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_single_file())