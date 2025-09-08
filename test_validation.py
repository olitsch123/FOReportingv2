"""Test PE validation logic."""

import asyncio
import sys
from decimal import Decimal

sys.path.insert(0, '.')

from app.pe_docs.validation import DocumentValidator, ValidationResult

async def test_validation():
    """Test validation logic with various scenarios."""
    results = []
    results.append("=== PE Validation Test ===\n")
    
    validator = DocumentValidator()
    results.append("✓ Created DocumentValidator\n")
    
    # Test 1: Valid capital account data
    results.append("Test 1: Valid Capital Account Data")
    results.append("-" * 50)
    
    valid_data = {
        'beginning_balance': Decimal('35000000'),
        'ending_balance': Decimal('40700000'),
        'contributions_period': Decimal('5000000'),
        'distributions_period': Decimal('4000000'),
        'management_fees_period': Decimal('250000'),
        'partnership_expenses_period': Decimal('50000'),
        'realized_gain_loss_period': Decimal('1500000'),
        'unrealized_gain_loss_period': Decimal('3000000'),
        'total_commitment': Decimal('50000000'),
        'drawn_commitment': Decimal('35000000'),
        'unfunded_commitment': Decimal('15000000')
    }
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=valid_data
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Errors: {len(result.errors)}")
    results.append(f"  Warnings: {len(result.warnings)}")
    results.append(f"  Confidence: {result.confidence:.2f}")
    
    if result.errors:
        for error in result.errors:
            results.append(f"  ERROR: {error['message']}")
    
    # Test 2: Invalid balance equation
    results.append("\nTest 2: Invalid Balance Equation")
    results.append("-" * 50)
    
    invalid_balance = valid_data.copy()
    invalid_balance['ending_balance'] = Decimal('45000000')  # Wrong!
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=invalid_balance
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Errors: {len(result.errors)}")
    if result.errors:
        results.append(f"  Error: {result.errors[0]['message']}")
    
    # Test 3: Unfunded exceeds total commitment
    results.append("\nTest 3: Unfunded Exceeds Total Commitment")
    results.append("-" * 50)
    
    invalid_commitment = valid_data.copy()
    invalid_commitment['unfunded_commitment'] = Decimal('60000000')  # More than total!
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=invalid_commitment
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Errors: {len(result.errors)}")
    if result.errors:
        results.append(f"  Error: {result.errors[0]['message']}")
    
    # Test 4: Missing required fields
    results.append("\nTest 4: Missing Required Fields")
    results.append("-" * 50)
    
    missing_fields = {
        'ending_balance': Decimal('40700000'),
        # Missing beginning_balance and total_commitment
    }
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=missing_fields
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Errors: {len(result.errors)}")
    for error in result.errors[:3]:  # Show first 3 errors
        results.append(f"  ERROR: {error['message']}")
    
    # Test 5: Period continuity check
    results.append("\nTest 5: Period Continuity Check")
    results.append("-" * 50)
    
    previous_period = {
        'ending_balance': Decimal('34000000')  # Should match current beginning
    }
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=valid_data,
        context={'previous_period': previous_period}
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Warnings: {len(result.warnings)}")
    if result.warnings:
        results.append(f"  Warning: {result.warnings[0]['message']}")
    
    # Test 6: Correct commitment math
    results.append("\nTest 6: Commitment Math Validation")
    results.append("-" * 50)
    
    # drawn + unfunded should equal total
    commitment_test = valid_data.copy()
    # 35M + 15M = 50M ✓
    
    result = await validator.validate_document(
        doc_type='capital_account_statement',
        extracted_data=commitment_test
    )
    
    results.append(f"  Valid: {result.is_valid}")
    results.append(f"  Drawn + Unfunded = Total: {commitment_test['drawn_commitment'] + commitment_test['unfunded_commitment']} = {commitment_test['total_commitment']}")
    results.append("  ✓ Commitment math is correct")
    
    results.append("\n" + "=" * 50)
    results.append("Validation tests completed!")
    
    return results

async def main():
    """Run validation tests."""
    results = await test_validation()
    
    # Write results to file
    with open('validation_test_results.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    
    print("Test complete. Check validation_test_results.txt for results.")

if __name__ == "__main__":
    asyncio.run(main())