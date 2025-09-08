"""Test processing a single PDF file."""

import os
import sys
import asyncio
from pathlib import Path

# Set UTF-8 encoding
os.environ['PYTHONUTF8'] = '1'
os.environ['PGCLIENTENCODING'] = 'UTF8'

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.pe_docs.api import handle_file

DATABASE_URL = os.getenv("DATABASE_URL")


async def test_single_pdf():
    """Test processing a single PDF."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("TESTING SINGLE PDF PROCESSING")
    print("=" * 50)
    
    # Find a PDF file
    test_file = Path(r"C:\Users\OliverGötz\Equivia GmbH\01_BrainWeb Investment GmbH - Dokumente\09 Funds\PE Club II\2. Credo Partners - PE Club AdCom October 2024.pdf")
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return
    
    print(f"\nTesting: {test_file.name}")
    print(f"Size: {test_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    try:
        # Process file
        result = await handle_file(str(test_file), "BRAINWEB", session)
        print(f"\nResult: {result}")
        
        if result and result.get('id'):
            doc_id = result['id']
            
            # Check database
            print(f"\nChecking database for doc_id: {doc_id}")
            
            # Check pe_document
            doc = session.execute(text(
                "SELECT * FROM pe_document WHERE doc_id = :doc_id"
            ), {"doc_id": doc_id}).fetchone()
            
            if doc:
                print(f"\nPE Document found:")
                print(f"  Type: {doc.doc_type}")
                print(f"  Fund ID: {doc.fund_id}")
                print(f"  Investor ID: {doc.investor_id}")
                print(f"  Embedding Status: {doc.embedding_status}")
                print(f"  Chunk Count: {doc.chunk_count}")
            
            # Check pe_capital_account
            accounts = session.execute(text(
                "SELECT COUNT(*) FROM pe_capital_account WHERE investor_id = :investor_id"
            ), {"investor_id": doc.investor_id if doc else "BRAINWEB"}).scalar()
            
            print(f"\nCapital Accounts: {accounts}")
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    session.close()


if __name__ == "__main__":
    asyncio.run(test_single_pdf())