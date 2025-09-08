"""Test PE reconciliation calculations."""

import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, '.')

from app.pe_docs.reconciliation.performance_reconciler import PerformanceReconciler

def test_irr_calculation():
    """Test IRR calculation logic."""
    results = []
    results.append("=== IRR Calculation Test ===\n")
    
    reconciler = PerformanceReconciler()
    results.append("✓ Created PerformanceReconciler\n")
    
    # Test 1: Simple IRR calculation
    results.append("Test 1: Simple IRR Calculation")
    results.append("-" * 50)
    
    # Initial investment of -100, return of 110 after 1 year = 10% IRR
    cashflows = [
        {'date': date(2022, 1, 1), 'amount': -100.0, 'type': 'contribution'},
        {'date': date(2023, 1, 1), 'amount': 110.0, 'type': 'distribution'}
    ]
    
    irr = reconciler._calculate_irr(cashflows, date(2023, 1, 1))
    results.append(f"  Cashflows: -100 at start, +110 after 1 year")
    results.append(f"  Calculated IRR: {irr:.2%}")
    results.append(f"  Expected IRR: 10.00%")
    results.append(f"  {'✓ Correct' if abs(irr - 0.10) < 0.001 else '✗ Incorrect'}")
    
    # Test 2: Multiple cashflows
    results.append("\nTest 2: Multiple Cashflows")
    results.append("-" * 50)
    
    cashflows = [
        {'date': date(2020, 1, 1), 'amount': -1000.0, 'type': 'contribution'},
        {'date': date(2020, 7, 1), 'amount': -500.0, 'type': 'contribution'},
        {'date': date(2021, 1, 1), 'amount': 300.0, 'type': 'distribution'},
        {'date': date(2021, 7, 1), 'amount': 400.0, 'type': 'distribution'},
        {'date': date(2022, 1, 1), 'amount': 1200.0, 'type': 'nav'}
    ]
    
    irr = reconciler._calculate_irr(cashflows, date(2022, 1, 1))
    results.append(f"  Initial: -1000, Additional: -500, Distributions: 700, Final NAV: 1200")
    results.append(f"  Calculated IRR: {irr:.2%}")
    results.append(f"  Expected range: 15-25% (good PE return)")
    results.append(f"  {'✓ Reasonable' if 0.15 <= irr <= 0.25 else '✗ Unusual'}")
    
    # Test 3: Negative IRR
    results.append("\nTest 3: Negative IRR")
    results.append("-" * 50)
    
    cashflows = [
        {'date': date(2020, 1, 1), 'amount': -1000.0, 'type': 'contribution'},
        {'date': date(2022, 1, 1), 'amount': 800.0, 'type': 'nav'}  # Loss
    ]
    
    irr = reconciler._calculate_irr(cashflows, date(2022, 1, 1))
    results.append(f"  Initial: -1000, Final: 800 (20% loss)")
    results.append(f"  Calculated IRR: {irr:.2%}")
    results.append(f"  {'✓ Correctly negative' if irr < 0 else '✗ Should be negative'}")
    
    # Test 4: Multiple calculation
    results.append("\nTest 4: Multiple Calculations (MOIC, TVPI, DPI)")
    results.append("-" * 50)
    
    test_cashflows = [
        {'date': date(2020, 1, 1), 'amount': -10000000.0, 'type': 'contribution'},
        {'date': date(2020, 7, 1), 'amount': -5000000.0, 'type': 'contribution'},
        {'date': date(2021, 6, 1), 'amount': 3000000.0, 'type': 'distribution'},
        {'date': date(2022, 6, 1), 'amount': 5000000.0, 'type': 'distribution'},
        {'date': date(2023, 12, 31), 'amount': 25000000.0, 'type': 'nav'}
    ]
    
    metrics = reconciler._calculate_metrics(test_cashflows, date(2023, 12, 31))
    
    results.append(f"  Total Contributions: ${metrics['total_contributions']:,.0f}")
    results.append(f"  Total Distributions: ${metrics['total_distributions']:,.0f}")
    results.append(f"  Current NAV: ${metrics['current_nav']:,.0f}")
    results.append(f"  MOIC: {metrics['moic_net']:.2f}x")
    results.append(f"  TVPI: {metrics['tvpi']:.2f}x")
    results.append(f"  DPI: {metrics['dpi']:.2f}x")
    results.append(f"  RVPI: {metrics['rvpi']:.2f}x")
    
    # Verify TVPI = DPI + RVPI
    tvpi_check = metrics['dpi'] + metrics['rvpi']
    results.append(f"\n  TVPI Check: {metrics['tvpi']:.2f} = {metrics['dpi']:.2f} + {metrics['rvpi']:.2f}")
    results.append(f"  {'✓ TVPI math correct' if abs(metrics['tvpi'] - tvpi_check) < 0.01 else '✗ TVPI math error'}")
    
    # Test 5: Comparison validation
    results.append("\nTest 5: Metrics Comparison")
    results.append("-" * 50)
    
    reported_metrics = {
        'irr_net': 0.185,  # 18.5%
        'moic_net': 2.20,
        'tvpi': 2.20,
        'dpi': 0.53,
        'rvpi': 1.67
    }
    
    calculated_metrics = {
        'irr_net': 0.182,  # 18.2% - close
        'moic_net': 2.21,
        'tvpi': 2.20,
        'dpi': 0.53,
        'rvpi': 1.67
    }
    
    comparison = reconciler._compare_metrics(reported_metrics, calculated_metrics)
    
    results.append(f"  Comparison Status: {comparison['status']}")
    results.append(f"  Discrepancies: {len(comparison['discrepancies'])}")
    results.append(f"  Confidence: {comparison['confidence']:.1f}")
    
    for disc in comparison['discrepancies']:
        results.append(f"  - {disc['metric']}: {disc['reported']} vs {disc['calculated']} (diff: {disc['difference']})")
    
    results.append("\n" + "=" * 50)
    results.append("Reconciliation tests completed!")
    
    return results

def main():
    """Run reconciliation tests."""
    results = test_irr_calculation()
    
    # Write results to file
    with open('reconciliation_test_results.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    
    print("Test complete. Check reconciliation_test_results.txt for results.")

if __name__ == "__main__":
    main()