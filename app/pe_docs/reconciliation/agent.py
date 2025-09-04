"""Automated reconciliation agent for PE documents."""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import uuid
import logging
from decimal import Decimal

from app.database.connection import get_db_session
from app.pe_docs.storage.orm import PEStorageORM
from .nav_reconciler import NAVReconciler
from .performance_reconciler import PerformanceReconciler

logger = logging.getLogger(__name__)


class ReconciliationAgent:
    """Automated reconciliation agent for PE data."""
    
    def __init__(self):
        """Initialize reconciliation agent."""
        self.nav_reconciler = NAVReconciler()
        self.performance_reconciler = PerformanceReconciler()
        self.storage = PEStorageORM()
    
    async def run_comprehensive_reconciliation(
        self,
        fund_id: str,
        as_of_date: date,
        reconciliation_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive reconciliation checks for a fund."""
        
        reconciliation_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        results = []
        
        # Default to all reconciliation types
        if not reconciliation_types:
            reconciliation_types = ["nav", "cashflow", "performance", "commitment"]
        
        try:
            # 1. NAV reconciliation (QR vs CAS)
            if "nav" in reconciliation_types:
                nav_result = await self.reconcile_nav(fund_id, as_of_date)
                results.append(nav_result)
            
            # 2. Cashflow reconciliation
            if "cashflow" in reconciliation_types:
                cf_result = await self.reconcile_cashflows(fund_id, as_of_date)
                results.append(cf_result)
            
            # 3. Performance metrics recalculation
            if "performance" in reconciliation_types:
                perf_result = await self.reconcile_performance(fund_id, as_of_date)
                results.append(perf_result)
            
            # 4. Commitment tracking
            if "commitment" in reconciliation_types:
                commit_result = await self.reconcile_commitments(fund_id, as_of_date)
                results.append(commit_result)
            
            # Store reconciliation results
            await self._store_reconciliation_results(reconciliation_id, results)
            
            # Determine overall status
            critical_issues = [r for r in results if r.get('status') == 'FAIL']
            warnings = [r for r in results if r.get('status') == 'WARNING']
            
            # Create summary
            summary = {
                'reconciliation_id': reconciliation_id,
                'fund_id': fund_id,
                'as_of_date': as_of_date,
                'start_time': start_time,
                'end_time': datetime.utcnow(),
                'duration_seconds': (datetime.utcnow() - start_time).total_seconds(),
                'reconciliation_types': reconciliation_types,
                'results': results,
                'summary': {
                    'total_checks': len(results),
                    'passed': len([r for r in results if r.get('status') == 'PASS']),
                    'warnings': len(warnings),
                    'failures': len(critical_issues)
                },
                'overall_status': 'FAIL' if critical_issues else ('WARNING' if warnings else 'PASS'),
                'requires_review': len(critical_issues) > 0 or len(warnings) > 2
            }
            
            # Send alerts if needed
            if critical_issues:
                await self._send_reconciliation_alert(fund_id, critical_issues, reconciliation_id)
            
            logger.info(
                f"Reconciliation completed for fund {fund_id}. "
                f"Status: {summary['overall_status']}, "
                f"Failures: {len(critical_issues)}, "
                f"Warnings: {len(warnings)}"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Reconciliation error for fund {fund_id}: {e}", exc_info=True)
            return {
                'reconciliation_id': reconciliation_id,
                'fund_id': fund_id,
                'as_of_date': as_of_date,
                'status': 'ERROR',
                'error': str(e)
            }
    
    async def reconcile_nav(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile NAV across different document types."""
        try:
            result = await self.nav_reconciler.reconcile(fund_id, as_of_date)
            return result
        except Exception as e:
            logger.error(f"NAV reconciliation error: {e}")
            return {
                'type': 'nav_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def reconcile_cashflows(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile cashflows for consistency."""
        try:
            with get_db_session() as db:
                # Get cashflow data for the period
                query = """
                    SELECT 
                        SUM(contributions_period) as total_contributions,
                        SUM(distributions_period) as total_distributions,
                        SUM(management_fees_period) as total_fees,
                        COUNT(*) as period_count
                    FROM pe_capital_account
                    WHERE fund_id = :fund_id
                    AND as_of_date BETWEEN :start_date AND :end_date
                """
                
                # Use last 4 quarters
                start_date = as_of_date - timedelta(days=365)
                
                result = db.execute(query, {
                    'fund_id': fund_id,
                    'start_date': start_date,
                    'end_date': as_of_date
                }).fetchone()
                
                if not result or result.period_count == 0:
                    return {
                        'type': 'cashflow_reconciliation',
                        'status': 'NO_DATA',
                        'message': 'No cashflow data found for period'
                    }
                
                # Basic checks
                checks_passed = True
                issues = []
                
                # Check for negative contributions
                if result.total_contributions and result.total_contributions < 0:
                    checks_passed = False
                    issues.append("Negative total contributions detected")
                
                # Check fee reasonableness (typically 0.5-2.5% quarterly)
                if result.total_fees and result.total_contributions:
                    fee_rate = float(result.total_fees) / float(result.total_contributions)
                    if fee_rate > 0.025 * result.period_count:  # More than 2.5% per period
                        issues.append(f"High fee rate detected: {fee_rate:.2%}")
                
                return {
                    'type': 'cashflow_reconciliation',
                    'status': 'PASS' if checks_passed else 'WARNING',
                    'total_contributions': float(result.total_contributions or 0),
                    'total_distributions': float(result.total_distributions or 0),
                    'total_fees': float(result.total_fees or 0),
                    'period_count': result.period_count,
                    'issues': issues
                }
                
        except Exception as e:
            logger.error(f"Cashflow reconciliation error: {e}")
            return {
                'type': 'cashflow_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def reconcile_performance(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile and recalculate performance metrics."""
        try:
            result = await self.performance_reconciler.reconcile(fund_id, as_of_date)
            return result
        except Exception as e:
            logger.error(f"Performance reconciliation error: {e}")
            return {
                'type': 'performance_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def reconcile_commitments(self, fund_id: str, as_of_date: date) -> Dict[str, Any]:
        """Reconcile commitment tracking."""
        try:
            with get_db_session() as db:
                # Get commitment data
                query = """
                    SELECT 
                        investor_id,
                        total_commitment,
                        drawn_commitment,
                        unfunded_commitment,
                        ending_balance
                    FROM pe_capital_account
                    WHERE fund_id = :fund_id
                    AND as_of_date = :as_of_date
                """
                
                results = db.execute(query, {
                    'fund_id': fund_id,
                    'as_of_date': as_of_date
                }).fetchall()
                
                if not results:
                    return {
                        'type': 'commitment_reconciliation',
                        'status': 'NO_DATA',
                        'message': 'No commitment data found'
                    }
                
                issues = []
                investor_issues = 0
                
                for row in results:
                    # Check commitment math
                    if row.total_commitment and row.drawn_commitment and row.unfunded_commitment:
                        expected_unfunded = Decimal(str(row.total_commitment)) - Decimal(str(row.drawn_commitment))
                        actual_unfunded = Decimal(str(row.unfunded_commitment))
                        
                        if abs(expected_unfunded - actual_unfunded) > 1:
                            investor_issues += 1
                            issues.append({
                                'investor_id': row.investor_id,
                                'type': 'commitment_math',
                                'expected_unfunded': float(expected_unfunded),
                                'actual_unfunded': float(actual_unfunded)
                            })
                    
                    # Check over-commitment
                    if row.drawn_commitment and row.total_commitment:
                        if Decimal(str(row.drawn_commitment)) > Decimal(str(row.total_commitment)):
                            investor_issues += 1
                            issues.append({
                                'investor_id': row.investor_id,
                                'type': 'over_commitment',
                                'drawn': float(row.drawn_commitment),
                                'total': float(row.total_commitment)
                            })
                
                return {
                    'type': 'commitment_reconciliation',
                    'status': 'FAIL' if investor_issues > 0 else 'PASS',
                    'total_investors': len(results),
                    'investors_with_issues': investor_issues,
                    'issues': issues[:10]  # Limit to first 10 issues
                }
                
        except Exception as e:
            logger.error(f"Commitment reconciliation error: {e}")
            return {
                'type': 'commitment_reconciliation',
                'status': 'ERROR',
                'message': str(e)
            }
    
    async def _store_reconciliation_results(
        self,
        reconciliation_id: str,
        results: List[Dict[str, Any]]
    ):
        """Store reconciliation results in database."""
        try:
            with get_db_session() as db:
                for result in results:
                    stmt = """
                        INSERT INTO reconciliation_log (
                            reconciliation_id,
                            doc_id,
                            reconciliation_type,
                            status,
                            differences,
                            confidence_score,
                            requires_review,
                            created_at
                        ) VALUES (
                            :reconciliation_id,
                            :doc_id,
                            :reconciliation_type,
                            :status,
                            :differences,
                            :confidence_score,
                            :requires_review,
                            :created_at
                        )
                    """
                    
                    db.execute(stmt, {
                        'reconciliation_id': reconciliation_id,
                        'doc_id': result.get('doc_id', reconciliation_id),  # Use reconciliation_id if no specific doc
                        'reconciliation_type': result.get('type'),
                        'status': result.get('status'),
                        'differences': result,  # Store full result as JSON
                        'confidence_score': result.get('confidence', 1.0),
                        'requires_review': result.get('status') in ['FAIL', 'ERROR'],
                        'created_at': datetime.utcnow()
                    })
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error storing reconciliation results: {e}")
    
    async def _send_reconciliation_alert(
        self,
        fund_id: str,
        critical_issues: List[Dict[str, Any]],
        reconciliation_id: str
    ):
        """Send alert for critical reconciliation issues."""
        # In production, this would send email/slack/etc notifications
        logger.warning(
            f"RECONCILIATION ALERT - Fund: {fund_id}, "
            f"Reconciliation ID: {reconciliation_id}, "
            f"Critical Issues: {len(critical_issues)}"
        )
        
        for issue in critical_issues:
            logger.warning(f"  - {issue.get('type')}: {issue.get('message', 'No details')}")
    
    async def run_daily_reconciliation(self):
        """Run daily reconciliation for all active funds."""
        try:
            with get_db_session() as db:
                # Get all funds with recent activity
                query = """
                    SELECT DISTINCT fund_id, MAX(as_of_date) as latest_date
                    FROM pe_capital_account
                    WHERE as_of_date >= :cutoff_date
                    GROUP BY fund_id
                """
                
                cutoff_date = date.today() - timedelta(days=90)
                results = db.execute(query, {'cutoff_date': cutoff_date}).fetchall()
                
                logger.info(f"Running daily reconciliation for {len(results)} funds")
                
                # Run reconciliation for each fund
                for row in results:
                    try:
                        await self.run_comprehensive_reconciliation(
                            fund_id=row.fund_id,
                            as_of_date=row.latest_date
                        )
                    except Exception as e:
                        logger.error(f"Error reconciling fund {row.fund_id}: {e}")
                        continue
                
                logger.info("Daily reconciliation completed")
                
        except Exception as e:
            logger.error(f"Daily reconciliation error: {e}", exc_info=True)