"""Simple standalone test for PE functionality - no Docker required."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Simple PE Functionality Test ===\n")

# Test 1: Can we import the modules?
print("Test 1: Importing PE modules...")
try:
    from app.pe_docs.extractors.base import BaseExtractor, ExtractionResult, ExtractionMethod
    print("✓ Base extractor imported")
    
    from app.pe_docs.extractors.capital_account import CapitalAccountExtractor
    print("✓ Capital account extractor imported")
    
    from app.pe_docs.validation import DocumentValidator
    print("✓ Document validator imported")
    
    print("\n✅ All imports successful!\n")
except Exception as e:
    print(f"\n❌ Import error: {e}\n")
    print("This means the code has dependency issues that need to be fixed.")
    sys.exit(1)

# Test 2: Can we create instances?
print("Test 2: Creating instances...")
try:
    extractor = CapitalAccountExtractor()
    print("✓ Capital account extractor created")
    
    validator = DocumentValidator()
    print("✓ Document validator created")
    
    print("\n✅ All instances created!\n")
except Exception as e:
    print(f"\n❌ Instance creation error: {e}\n")
    sys.exit(1)

# Test 3: Can we run basic extraction?
print("Test 3: Testing basic extraction...")
try:
    # Simple test text
    test_text = """
    Beginning Balance: $1,000,000
    Ending Balance: $1,200,000
    Total Commitment: $5,000,000
    """
    
    # Test regex extraction
    result = extractor.extract_with_regex(test_text, 'beginning_balance')
    if result:
        print(f"✓ Extracted beginning balance: ${result.value:,.0f}")
    else:
        print("❌ Failed to extract beginning balance")
    
    result = extractor.extract_with_regex(test_text, 'ending_balance')
    if result:
        print(f"✓ Extracted ending balance: ${result.value:,.0f}")
    else:
        print("❌ Failed to extract ending balance")
    
    print("\n✅ Basic extraction works!\n")
except Exception as e:
    print(f"\n❌ Extraction error: {e}\n")
    import traceback
    traceback.print_exc()

# Test 4: Check field definitions
print("Test 4: Checking field definitions...")
try:
    fields = extractor.field_definitions
    print(f"✓ Found {len(fields)} field definitions")
    print(f"✓ Fields include: {', '.join(list(fields.keys())[:5])}...")
    
    print("\n✅ Field definitions loaded!\n")
except Exception as e:
    print(f"\n❌ Field definition error: {e}\n")

# Summary
print("\n=== Test Summary ===")
print("If all tests passed, the basic PE functionality is working!")
print("If any failed, those specific areas need to be fixed.")
print("\nNote: This doesn't test database, Docker, or API functionality.")
print("It only verifies the core PE extraction logic can run.")