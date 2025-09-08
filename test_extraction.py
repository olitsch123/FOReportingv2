"""Test PE extraction on sample documents."""

import asyncio
import sys
import os
from datetime import date
from pathlib import Path

sys.path.insert(0, '.')

from app.pe_docs.extractors.capital_account import CapitalAccountExtractor

async def test_capital_account_extraction():
    """Test extraction on sample capital account statement."""
    results = []
    results.append("=== Capital Account Extraction Test ===\n")
    
    try:
        # Read sample document
        doc_path = Path("data/test_documents/sample_capital_account.txt")
        if not doc_path.exists():
            results.append(f"ERROR: Sample document not found at {doc_path}")
            return results
            
        with open(doc_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        results.append(f"✓ Loaded document: {doc_path}")
        results.append(f"  Document length: {len(text)} characters\n")
        
        # Create extractor
        extractor = CapitalAccountExtractor()
        results.append("✓ Created CapitalAccountExtractor\n")
        
        # Test individual field extractions
        test_fields = [
            'beginning_balance',
            'ending_balance', 
            'contributions_period',
            'distributions_period',
            'management_fees_period',
            'partnership_expenses_period',
            'realized_gain_loss_period',
            'unrealized_gain_loss_period',
            'total_commitment',
            'drawn_commitment',
            'unfunded_commitment',
            'ownership_pct'
        ]
        
        results.append("Field Extraction Results:")
        results.append("-" * 50)
        
        extracted_values = {}
        for field in test_fields:
            result = extractor.extract_with_regex(text, field)
            if result:
                extracted_values[field] = result.value
                results.append(f"✓ {field:30} = {result.value:>15}")
                results.append(f"  Method: {result.method}, Confidence: {result.confidence}")
            else:
                results.append(f"✗ {field:30} = NOT FOUND")
        
        results.append("\n" + "=" * 50)
        
        # Run full extraction
        results.append("\nRunning full extraction...")
        try:
            full_result = await extractor.extract(
                text=text,
                tables=[],  # No tables in text format
                doc_type='capital_account_statement'
            )
            
            results.append("✓ Full extraction completed")
            results.append(f"  Fields extracted: {len(full_result)}")
            
            # Compare expected vs actual values
            expected_values = {
                'beginning_balance': 35000000,
                'ending_balance': 40700000,
                'contributions_period': 5000000,
                'distributions_period': 4000000,
                'management_fees_period': 250000,
                'partnership_expenses_period': 50000,
                'realized_gain_loss_period': 1500000,
                'unrealized_gain_loss_period': 3000000,
                'total_commitment': 50000000,
                'drawn_commitment': 35000000,
                'unfunded_commitment': 15000000,
                'ownership_pct': 0.05  # 5% as decimal
            }
            
            results.append("\nAccuracy Check:")
            results.append("-" * 50)
            
            correct_count = 0
            total_count = 0
            
            for field, expected in expected_values.items():
                if field in extracted_values:
                    actual = float(extracted_values[field])
                    if field == 'ownership_pct':
                        # For percentage, compare as decimal
                        is_correct = abs(actual - expected) < 0.001
                    else:
                        # For amounts, exact match
                        is_correct = actual == expected
                    
                    total_count += 1
                    if is_correct:
                        correct_count += 1
                        results.append(f"✓ {field}: {actual} (correct)")
                    else:
                        results.append(f"✗ {field}: {actual} (expected {expected})")
                else:
                    total_count += 1
                    results.append(f"✗ {field}: NOT EXTRACTED (expected {expected})")
            
            accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
            results.append(f"\nAccuracy: {correct_count}/{total_count} = {accuracy:.1f}%")
            
        except Exception as e:
            results.append(f"\n✗ Full extraction failed: {e}")
            import traceback
            results.append(traceback.format_exc())
            
    except Exception as e:
        results.append(f"\n✗ Test failed: {e}")
        import traceback
        results.append(traceback.format_exc())
    
    return results

async def main():
    """Run all extraction tests."""
    all_results = []
    
    # Test capital account extraction
    cas_results = await test_capital_account_extraction()
    all_results.extend(cas_results)
    
    # Write results to file
    with open('extraction_test_results.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_results))
    
    print("Test complete. Check extraction_test_results.txt for results.")

if __name__ == "__main__":
    asyncio.run(main())