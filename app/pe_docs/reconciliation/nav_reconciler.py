"""NAV reconciliation between different document types."""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from app.database.connection import get_db_session

logger = logging.getLogger(__name__)


class NAVReconciler:
    """Reconcile NAV values across different document types."""
    
    def __init__(self):
        """Initialize NAV reconciler."""
        self.tolerance_pct = Decimal('0.001')  # 0.1% tolerance
        self.tolerance_abs = Decimal('100')    # $100 absolute tolerance
    
    async def reconcile(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile NAV between quarterly report and capital account statement."""
        
        try:
            # Get NAV from capital account statement
            cas_nav = await self._get_cas_nav(fund_id, as_of_date)
            
            # Get NAV from financial data (quarterly report)
            qr_nav = await self._get_qr_nav(fund_id, as_of_date)
            
            # Get NAV from performance metrics
            perf_nav = await self._get_performance_nav(fund_id, as_of_date)
            
            # Collect all NAV values
            nav_sources = []
            if cas_nav is not None:
                nav_sources.append({'source': 'capital_account', 'value': cas_nav})
            if qr_nav is not None:
                nav_sources.append({'source': 'quarterly_report', 'value': qr_nav})
            if perf_nav is not None:
                nav_sources.append({'source': 'performance_metrics', 'value': perf_nav})
            
            if len(nav_sources) < 2:
                return {
                    'type': 'nav_reconciliation',
                    'status': 'INSUFFICIENT_DATA',
                    'message': f'Only {len(nav_sources)} NAV source(s) found',
                    'sources': nav_sources
                }
            
            # Compare NAV values
            reconciliation_result = self._compare_nav_values(nav_sources)
            
            return reconciliation_result
            
        except Exception as e:
            logger.error(f"NAV reconciliation error: {e}", exc_info=True)
            return {
                'type': 'nav_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def _get_cas_nav(self, fund_id: str, as_of_date: date) -> Optional[Decimal]:
        """Get NAV from capital account statement."""
        with get_db_session() as db:
            query = """
                SELECT SUM(ending_balance) as total_nav
                FROM pe_capital_account
                WHERE fund_id = :fund_id
                AND as_of_date = :as_of_date
                GROUP BY fund_id, as_of_date
            """
            
            result = db.execute(query, {
                'fund_id': fund_id,
                'as_of_date': as_of_date
            }).fetchone()
            
            if result and result.total_nav is not None:
                return Decimal(str(result.total_nav))
            
            return None
    
    async def _get_qr_nav(self, fund_id: str, as_of_date: date) -> Optional[Decimal]:
        """Get NAV from quarterly report (financial_data table)."""
        with get_db_session() as db:
            query = """
                SELECT nav
                FROM financial_data
                WHERE fund_id = :fund_id
                AND DATE(reporting_date) = :as_of_date
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = db.execute(query, {
                'fund_id': fund_id,
                'as_of_date': as_of_date
            }).fetchone()
            
            if result and result.nav is not None:
                return Decimal(str(result.nav))
            
            return None
    
    async def _get_performance_nav(self, fund_id: str, as_of_date: date) -> Optional[Decimal]:
        """Get NAV from performance metrics table."""
        with get_db_session() as db:
            query = """
                SELECT 
                    SUM(ca.ending_balance) as calculated_nav
                FROM pe_capital_account ca
                JOIN pe_performance_metrics pm ON pm.fund_id = ca.fund_id 
                    AND pm.as_of_date = ca.as_of_date
                WHERE ca.fund_id = :fund_id
                AND ca.as_of_date = :as_of_date
                GROUP BY ca.fund_id, ca.as_of_date
            """
            
            result = db.execute(query, {
                'fund_id': fund_id,
                'as_of_date': as_of_date
            }).fetchone()
            
            if result and result.calculated_nav is not None:
                return Decimal(str(result.calculated_nav))
            
            return None
    
    def _compare_nav_values(self, nav_sources: list) -> Dict[str, Any]:
        """Compare NAV values from different sources."""
        
        # Calculate average NAV
        total_nav = sum(s['value'] for s in nav_sources)
        avg_nav = total_nav / len(nav_sources)
        
        # Check each source against average
        discrepancies = []
        max_deviation = Decimal('0')
        
        for source in nav_sources:
            deviation = abs(source['value'] - avg_nav)
            deviation_pct = (deviation / avg_nav * 100) if avg_nav > 0 else Decimal('0')
            
            # Check if within tolerance
            within_pct_tolerance = deviation_pct <= (self.tolerance_pct * 100)
            within_abs_tolerance = deviation <= self.tolerance_abs
            within_tolerance = within_pct_tolerance or within_abs_tolerance
            
            if not within_tolerance:
                discrepancies.append({
                    'source': source['source'],
                    'value': float(source['value']),
                    'deviation': float(deviation),
                    'deviation_pct': float(deviation_pct)
                })
            
            max_deviation = max(max_deviation, deviation_pct)
        
        # Determine status
        if not discrepancies:
            status = 'PASS'
            message = 'All NAV sources within tolerance'
        elif max_deviation < 1:  # Less than 1% deviation
            status = 'WARNING'
            message = f'Minor NAV discrepancies detected (max {float(max_deviation):.2f}%)'
        else:
            status = 'FAIL'
            message = f'Significant NAV discrepancies detected (max {float(max_deviation):.2f}%)'
        
        return {
            'type': 'nav_reconciliation',
            'status': status,
            'message': message,
            'average_nav': float(avg_nav),
            'sources': [
                {
                    'source': s['source'],
                    'value': float(s['value']),
                    'deviation_from_avg': float(abs(s['value'] - avg_nav)),
                    'deviation_pct': float((abs(s['value'] - avg_nav) / avg_nav * 100) if avg_nav > 0 else 0)
                }
                for s in nav_sources
            ],
            'discrepancies': discrepancies,
            'max_deviation_pct': float(max_deviation),
            'tolerance_pct': float(self.tolerance_pct * 100),
            'tolerance_abs': float(self.tolerance_abs)
        }