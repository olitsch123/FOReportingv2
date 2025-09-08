"""Performance metrics reconciliation and recalculation."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.optimize import newton

from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


class PerformanceReconciler:
    """Reconcile and recalculate performance metrics."""
    
    def __init__(self):
        """Initialize performance reconciler."""
        self.irr_tolerance = 0.001  # 0.1% IRR tolerance
        self.multiple_tolerance = 0.01  # 0.01x multiple tolerance
    
    async def reconcile(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile performance metrics by recalculating from cashflows."""
        
        try:
            # Get reported metrics
            reported_metrics = await self._get_reported_metrics(fund_id, as_of_date)
            
            # Get cashflow history
            cashflows = await self._get_cashflow_history(fund_id, as_of_date)
            
            if not cashflows:
                return {
                    'type': 'performance_reconciliation',
                    'status': 'NO_DATA',
                    'message': 'No cashflow data available for recalculation'
                }
            
            # Recalculate metrics
            calculated_metrics = self._calculate_metrics(cashflows, as_of_date)
            
            # Compare reported vs calculated
            comparison_result = self._compare_metrics(reported_metrics, calculated_metrics)
            
            return comparison_result
            
        except Exception as e:
            logger.error(f"Performance reconciliation error: {e}", exc_info=True)
            return {
                'type': 'performance_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def _get_reported_metrics(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Get reported performance metrics."""
        with get_db_session() as db:
            query = """
                SELECT 
                    irr_net,
                    moic_net,
                    tvpi,
                    dpi,
                    rvpi
                FROM pe_performance_metrics
                WHERE fund_id = :fund_id
                AND as_of_date = :as_of_date
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = db.execute(query, {
                'fund_id': fund_id,
                'as_of_date': as_of_date
            }).fetchone()
            
            if result:
                return {
                    'irr_net': float(result.irr_net) if result.irr_net else None,
                    'moic_net': float(result.moic_net) if result.moic_net else None,
                    'tvpi': float(result.tvpi) if result.tvpi else None,
                    'dpi': float(result.dpi) if result.dpi else None,
                    'rvpi': float(result.rvpi) if result.rvpi else None
                }
            
            return {}
    
    async def _get_cashflow_history(self, fund_id: str, as_of_date: date) -> List[Dict[str, Any]]:
        """Get complete cashflow history for IRR calculation."""
        with get_db_session() as db:
            query = """
                SELECT 
                    as_of_date,
                    contributions_period,
                    distributions_period,
                    ending_balance
                FROM pe_capital_account
                WHERE fund_id = :fund_id
                AND as_of_date <= :as_of_date
                ORDER BY as_of_date
            """
            
            results = db.execute(query, {
                'fund_id': fund_id,
                'as_of_date': as_of_date
            }).fetchall()
            
            cashflows = []
            for row in results:
                if row.contributions_period and row.contributions_period > 0:
                    cashflows.append({
                        'date': row.as_of_date,
                        'amount': -float(row.contributions_period),  # Negative for outflows
                        'type': 'contribution'
                    })
                
                if row.distributions_period and row.distributions_period > 0:
                    cashflows.append({
                        'date': row.as_of_date,
                        'amount': float(row.distributions_period),  # Positive for inflows
                        'type': 'distribution'
                    })
            
            # Add current NAV as final cashflow
            if results:
                last_row = results[-1]
                if last_row.ending_balance:
                    cashflows.append({
                        'date': as_of_date,
                        'amount': float(last_row.ending_balance),
                        'type': 'nav'
                    })
            
            return cashflows
    
    def _calculate_metrics(self, cashflows: List[Dict[str, Any]], as_of_date: date) -> Dict[str, Any]:
        """Calculate performance metrics from cashflows."""
        
        if not cashflows:
            return {}
        
        # Separate contributions and distributions
        contributions = sum(abs(cf['amount']) for cf in cashflows if cf['amount'] < 0)
        distributions = sum(cf['amount'] for cf in cashflows if cf['amount'] > 0 and cf['type'] == 'distribution')
        current_nav = next((cf['amount'] for cf in cashflows if cf['type'] == 'nav'), 0)
        
        # Calculate multiples
        if contributions > 0:
            moic = (distributions + current_nav) / contributions
            dpi = distributions / contributions
            rvpi = current_nav / contributions
            tvpi = dpi + rvpi
        else:
            moic = dpi = rvpi = tvpi = 0
        
        # Calculate IRR
        irr = self._calculate_irr(cashflows, as_of_date)
        
        return {
            'irr_net': irr,
            'moic_net': moic,
            'tvpi': tvpi,
            'dpi': dpi,
            'rvpi': rvpi,
            'total_contributions': contributions,
            'total_distributions': distributions,
            'current_nav': current_nav
        }
    
    def _calculate_irr(self, cashflows: List[Dict[str, Any]], as_of_date: date) -> float:
        """Calculate IRR using Newton's method."""
        
        if len(cashflows) < 2:
            return 0.0
        
        # Convert to days from first cashflow
        first_date = min(cf['date'] for cf in cashflows)
        
        # Create time-weighted cashflow array
        cf_data = []
        for cf in cashflows:
            days = (cf['date'] - first_date).days
            years = days / 365.25
            cf_data.append((years, cf['amount']))
        
        # NPV function for IRR calculation
        def npv(rate):
            return sum(amount / ((1 + rate) ** time) for time, amount in cf_data)
        
        # NPV derivative for Newton's method
        def npv_derivative(rate):
            return sum(-time * amount / ((1 + rate) ** (time + 1)) for time, amount in cf_data)
        
        try:
            # Try Newton's method with multiple starting points
            for initial_guess in [0.1, 0.0, -0.1, 0.2, -0.2]:
                try:
                    irr = newton(npv, initial_guess, fprime=npv_derivative, maxiter=100)
                    # Verify the solution
                    if abs(npv(irr)) < 0.01:  # Close enough to zero
                        return float(irr)
                except:
                    continue
            
            # If Newton's method fails, try simple bisection
            return self._irr_bisection(cf_data)
            
        except Exception as e:
            logger.warning(f"IRR calculation failed: {e}")
            return 0.0
    
    def _irr_bisection(self, cf_data: List[tuple]) -> float:
        """Calculate IRR using bisection method as fallback."""
        
        def npv(rate):
            return sum(amount / ((1 + rate) ** time) for time, amount in cf_data)
        
        # Find bounds
        low, high = -0.99, 5.0
        
        # Check if solution exists
        if npv(low) * npv(high) > 0:
            return 0.0
        
        # Bisection
        for _ in range(100):
            mid = (low + high) / 2
            npv_mid = npv(mid)
            
            if abs(npv_mid) < 0.01:
                return mid
            
            if npv(low) * npv_mid < 0:
                high = mid
            else:
                low = mid
        
        return (low + high) / 2
    
    def _compare_metrics(self, reported: Dict[str, Any], calculated: Dict[str, Any]) -> Dict[str, Any]:
        """Compare reported vs calculated metrics."""
        
        discrepancies = []
        status = 'PASS'
        
        # Compare IRR
        if reported.get('irr_net') is not None and calculated.get('irr_net') is not None:
            irr_diff = abs(reported['irr_net'] - calculated['irr_net'])
            if irr_diff > self.irr_tolerance:
                status = 'WARNING' if irr_diff < 0.02 else 'FAIL'
                discrepancies.append({
                    'metric': 'IRR',
                    'reported': f"{reported['irr_net']:.2%}",
                    'calculated': f"{calculated['irr_net']:.2%}",
                    'difference': f"{irr_diff:.2%}"
                })
        
        # Compare multiples
        for metric in ['moic_net', 'tvpi', 'dpi', 'rvpi']:
            if reported.get(metric) is not None and calculated.get(metric) is not None:
                diff = abs(reported[metric] - calculated[metric])
                if diff > self.multiple_tolerance:
                    status = 'WARNING' if status == 'PASS' else status
                    discrepancies.append({
                        'metric': metric.upper(),
                        'reported': f"{reported[metric]:.2f}x",
                        'calculated': f"{calculated[metric]:.2f}x",
                        'difference': f"{diff:.2f}x"
                    })
        
        # Check TVPI = DPI + RVPI
        if all(k in calculated for k in ['tvpi', 'dpi', 'rvpi']):
            tvpi_check = abs(calculated['tvpi'] - (calculated['dpi'] + calculated['rvpi']))
            if tvpi_check > 0.001:
                status = 'WARNING' if status == 'PASS' else status
                discrepancies.append({
                    'metric': 'TVPI_CHECK',
                    'message': f"TVPI ({calculated['tvpi']:.2f}) != DPI ({calculated['dpi']:.2f}) + RVPI ({calculated['rvpi']:.2f})"
                })
        
        return {
            'type': 'performance_reconciliation',
            'status': status,
            'message': f"{len(discrepancies)} discrepancies found" if discrepancies else "All metrics reconciled",
            'reported_metrics': reported,
            'calculated_metrics': {
                k: round(v, 4) if isinstance(v, float) else v 
                for k, v in calculated.items()
            },
            'discrepancies': discrepancies,
            'confidence': 0.9 if status == 'PASS' else (0.7 if status == 'WARNING' else 0.5)
        }