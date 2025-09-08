"""Simple PE test that can be run inside Docker via exec."""

print("Testing PE functionality in Docker...")

# Test 1: Database connection
print("\n1. Testing database connection:")
try:
    from app.database.connection import get_engine
    from sqlalchemy import text
    
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        print("   ✓ Database connected successfully")
        
        # Check if PE tables exist
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'pe_%'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        print(f"   ✓ Found {len(tables)} PE tables:")
        for table in tables[:5]:  # Show first 5
            print(f"     - {table}")
        if len(tables) > 5:
            print(f"     ... and {len(tables) - 5} more")
except Exception as e:
    print(f"   ✗ Database error: {e}")

# Test 2: PE module imports
print("\n2. Testing PE module imports:")
try:
    from app.pe_docs.extractors.multi_method import MultiMethodExtractor
    from app.pe_docs.validation import DocumentValidator
    from app.pe_docs.storage.orm import PEStorageORM
    print("   ✓ All PE modules imported successfully")
except Exception as e:
    print(f"   ✗ Import error: {e}")

# Test 3: Simple extraction test
print("\n3. Testing extraction on sample text:")
try:
    from app.pe_docs.extractors.capital_account import CapitalAccountExtractor
    import asyncio
    
    sample_text = """
    Beginning Balance: $35,000,000.00
    Ending Balance: $40,700,000.00
    Total Commitment: $50,000,000.00
    """
    
    async def test_extraction():
        extractor = CapitalAccountExtractor()
        results = {}
        
        # Test field extraction
        for field in ['beginning_balance', 'ending_balance', 'total_commitment']:
            result = extractor.extract_with_regex(sample_text, field)
            if result:
                results[field] = float(result.value)
        
        return results
    
    results = asyncio.run(test_extraction())
    print(f"   ✓ Extracted {len(results)} fields:")
    for field, value in results.items():
        print(f"     - {field}: ${value:,.2f}")
        
except Exception as e:
    print(f"   ✗ Extraction error: {e}")

print("\n" + "="*50)
print("Docker PE test complete!")
print("="*50)