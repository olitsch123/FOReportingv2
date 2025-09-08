"""End-to-end test for PE document processing."""

import asyncio
import sys
import os
from pathlib import Path
from datetime import date
import json

sys.path.insert(0, '.')

from app.pe_docs.extractors.multi_method import MultiMethodExtractor

async def test_end_to_end():
    """Test complete document processing pipeline."""
    results = []
    results.append("=== End-to-End PE Document Processing Test ===\n")
    
    # Step 1: Load document
    results.append("Step 1: Load Document")
    results.append("-" * 50)
    
    doc_path = Path("data/test_documents/sample_capital_account.txt")
    if not doc_path.exists():
        results.append("✗ ERROR: Sample document not found")
        return results
    
    with open(doc_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    results.append(f"✓ Loaded: {doc_path}")
    results.append(f"  Size: {len(text)} characters\n")
    
    # Step 2: Initialize extractor
    results.append("Step 2: Initialize Multi-Method Extractor")
    results.append("-" * 50)
    
    try:
        extractor = MultiMethodExtractor()
        results.append("✓ MultiMethodExtractor initialized\n")
    except Exception as e:
        results.append(f"✗ ERROR: {e}")
        return results
    
    # Step 3: Process document
    results.append("Step 3: Process Document")
    results.append("-" * 50)
    
    doc_metadata = {
        'doc_id': 'test-doc-001',
        'doc_type': 'capital_account_statement',
        'filename': 'sample_capital_account.txt',
        'fund_id': '550e8400-e29b-41d4-a716-446655440000',
        'investor_id': 'test-investor-001',
        'period_end': date(2023, 12, 31),
        'as_of_date': date(2023, 12, 31)
    }
    
    try:
        result = await extractor.process_document(
            file_path=str(doc_path),
            text=text,
            tables=[],
            doc_metadata=doc_metadata
        )
        
        results.append(f"✓ Document processed successfully")
        results.append(f"  Status: {result['status']}")
        results.append(f"  Confidence: {result.get('overall_confidence', 0):.2f}")
        results.append(f"  Requires Review: {result.get('requires_review', False)}\n")
        
    except Exception as e:
        results.append(f"✗ ERROR processing document: {e}")
        import traceback
        results.append(traceback.format_exc())
        return results
    
    # Step 4: Check extraction results
    results.append("Step 4: Extraction Results")
    results.append("-" * 50)
    
    if result['status'] == 'success':
        extracted = result.get('extracted_data', {})
        
        key_fields = [
            'beginning_balance',
            'ending_balance',
            'contributions_period',
            'distributions_period',
            'total_commitment',
            'unfunded_commitment'
        ]
        
        for field in key_fields:
            value = extracted.get(field, 'NOT FOUND')
            results.append(f"  {field:25} = {value}")
        
        results.append(f"\n  Total fields extracted: {len(extracted)}")
        
        # Check extraction audit
        audit = extracted.get('extraction_audit', [])
        results.append(f"  Audit entries: {len(audit)}")
        
        if audit:
            results.append("\n  Sample audit entries:")
            for entry in audit[:3]:
                results.append(f"    - {entry['field']}: {entry['method']} (conf: {entry['confidence']})")
    
    # Step 5: Check validation results
    results.append("\nStep 5: Validation Results")
    results.append("-" * 50)
    
    validation = result.get('validation', {})
    results.append(f"  Valid: {validation.get('is_valid', False)}")
    results.append(f"  Errors: {len(validation.get('errors', []))}")
    results.append(f"  Warnings: {len(validation.get('warnings', []))}")
    results.append(f"  Confidence: {validation.get('confidence', 0):.2f}")
    
    if validation.get('errors'):
        results.append("\n  Validation errors:")
        for error in validation['errors'][:3]:
            results.append(f"    - {error.get('message', error)}")
    
    # Step 6: Simulate storage (would normally go to database)
    results.append("\nStep 6: Storage Simulation")
    results.append("-" * 50)
    
    if result['status'] == 'success':
        # In real system, this would call storage.upsert_capital_account()
        results.append("✓ Would store to pe_capital_account table")
        results.append("✓ Would create extraction_audit records")
        results.append("✓ Would update document status")
    else:
        results.append("✗ Document failed processing - would not store")
    
    # Step 7: Test manual override capability
    results.append("\nStep 7: Manual Override Test")
    results.append("-" * 50)
    
    corrections = {
        'ending_balance': 40700000,  # Correct value
        'distributions_period': 4000000  # Fix if wrong
    }
    
    try:
        override_result = await extractor.reprocess_with_corrections(
            doc_id='test-doc-001',
            corrections=corrections
        )
        
        if override_result['status'] == 'success':
            results.append("✓ Manual corrections applied successfully")
            results.append(f"  Corrected fields: {len(corrections)}")
        else:
            results.append(f"✗ Manual override failed: {override_result.get('error')}")
            
    except Exception as e:
        results.append(f"✗ ERROR in manual override: {e}")
    
    # Summary
    results.append("\n" + "=" * 50)
    results.append("End-to-End Test Summary")
    results.append("=" * 50)
    
    if result['status'] == 'success':
        results.append("✅ Document processing pipeline is WORKING!")
        results.append(f"   - Extraction: {result.get('overall_confidence', 0):.0%} confidence")
        results.append(f"   - Validation: {'Passed' if validation.get('is_valid') else 'Has issues'}")
        results.append(f"   - Ready for: {'Auto-processing' if not result.get('requires_review') else 'Manual review'}")
    else:
        results.append("❌ Document processing FAILED")
        results.append(f"   - Error: {result.get('error', 'Unknown')}")
    
    return results

async def main():
    """Run end-to-end test."""
    results = await test_end_to_end()
    
    # Write results to file
    with open('end_to_end_test_results.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    
    print("Test complete. Check end_to_end_test_results.txt for results.")

if __name__ == "__main__":
    asyncio.run(main())