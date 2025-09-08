"""Financial Reconciliation Agent using OpenAI Agents SDK."""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from agents import Agent, Runner, Tool
from sqlalchemy import text

from app.config import settings
from app.database.connection import get_db_session
from app.pe_docs.storage.orm import PEStorageORM
from app.pe_docs.storage.vector import PEVectorStore

logger = logging.getLogger(__name__)


class FinancialReconciliationAgent:
    """Sophisticated financial reconciliation agent using OpenAI Agents SDK."""
    
    def __init__(self):
        """Initialize the reconciliation agent with specialized tools."""
        self.vector_store = PEVectorStore()
        self.storage = PEStorageORM()
        
        # Create specialized financial analyst agent
        self.agent = Agent(
            name="Financial Reconciliation Analyst",
            instructions="""You are an expert financial analyst specializing in private equity reconciliation.
            
Your core responsibilities:
1. **Data Accuracy**: Compare data across multiple sources (database, vector store, original files) to ensure consistency
2. **Completeness Check**: Verify all required data points are present and properly captured
3. **KPI Validation**: Recalculate key performance indicators and flag any discrepancies
4. **Anomaly Detection**: Identify unusual patterns, outliers, or potential errors
5. **Compliance**: Ensure data meets regulatory and internal reporting standards

When analyzing data:
- Always compare at least 2 sources before confirming accuracy
- Calculate variances with precision (use 6 decimal places for percentages)
- Consider time-series consistency and trend analysis
- Flag any missing data that could impact reporting
- Provide clear, actionable recommendations

You have deep expertise in:
- NAV calculations and reconciliation
- IRR/MOIC/DPI calculations
- Capital account statements
- Fee calculations (management fees, carried interest)
- Waterfall distributions
- J-curve analysis

Always maintain professional skepticism and investigate any discrepancies thoroughly.""",
            tools=self._create_tools()
        )
    
    def _create_tools(self) -> List[Tool]:
        """Create specialized tools for financial reconciliation."""
        return [
            # Database tools
            Tool(
                name="fetch_nav_from_database",
                description="Fetch NAV data from database for a specific fund and date",
                func=self._fetch_nav_from_db
            ),
            Tool(
                name="fetch_cashflows_from_database", 
                description="Fetch cashflow data from database for a fund over a period",
                func=self._fetch_cashflows_from_db
            ),
            Tool(
                name="fetch_capital_accounts",
                description="Fetch capital account data for all investors in a fund",
                func=self._fetch_capital_accounts
            ),
            Tool(
                name="fetch_performance_metrics",
                description="Fetch performance metrics (IRR, MOIC, DPI) from database",
                func=self._fetch_performance_metrics
            ),
            
            # Vector store tools
            Tool(
                name="search_vector_store",
                description="Search vector store for relevant documents and data",
                func=self._search_vector_store
            ),
            Tool(
                name="fetch_document_content",
                description="Fetch specific document content from vector store",
                func=self._fetch_document_content
            ),
            
            # File reading tools
            Tool(
                name="read_original_file",
                description="Read and parse original source file (PDF, Excel, etc)",
                func=self._read_original_file
            ),
            
            # Calculation tools
            Tool(
                name="calculate_irr",
                description="Calculate IRR from cashflow series",
                func=self._calculate_irr
            ),
            Tool(
                name="calculate_moic",
                description="Calculate MOIC (Multiple on Invested Capital)",
                func=self._calculate_moic
            ),
            Tool(
                name="calculate_dpi",
                description="Calculate DPI (Distributions to Paid-In)",
                func=self._calculate_dpi
            ),
            Tool(
                name="validate_nav_components",
                description="Validate NAV calculation components",
                func=self._validate_nav_components
            ),
            
            # Reconciliation tools
            Tool(
                name="compare_values",
                description="Compare values with tolerance and return variance analysis",
                func=self._compare_values
            ),
            Tool(
                name="flag_discrepancy",
                description="Flag a discrepancy with severity and recommendations",
                func=self._flag_discrepancy
            ),
            Tool(
                name="generate_reconciliation_report",
                description="Generate comprehensive reconciliation report",
                func=self._generate_report
            )
        ]
    
    async def reconcile_fund(
        self,
        fund_id: str,
        as_of_date: date,
        reconciliation_scope: List[str] = None
    ) -> Dict[str, Any]:
        """Run comprehensive reconciliation for a fund."""
        
        if not reconciliation_scope:
            reconciliation_scope = ["nav", "cashflows", "performance", "capital_accounts"]
        
        # Prepare the reconciliation query
        query = f"""Please perform a comprehensive reconciliation for fund {fund_id} as of {as_of_date}.

Reconciliation Scope: {', '.join(reconciliation_scope)}

For each area:
1. Fetch data from multiple sources (database, vector store, original files if available)
2. Compare values and calculate variances
3. Validate calculations and KPIs
4. Flag any discrepancies with severity (CRITICAL, HIGH, MEDIUM, LOW)
5. Provide specific recommendations

Pay special attention to:
- NAV consistency across quarterly reports and capital account statements
- Cashflow timing and categorization
- Performance metric calculations (ensure IRR and MOIC are correctly calculated)
- Capital account balances and commitment tracking
- Fee calculations and accruals

Generate a detailed reconciliation report with all findings."""

        # Run the agent
        result = await Runner.run(
            self.agent,
            query,
            session_id=f"reconciliation_{fund_id}_{as_of_date}"
        )
        
        return result.final_output
    
    # Database fetch tools
    async def _fetch_nav_from_db(self, fund_id: str, as_of_date: str) -> Dict[str, Any]:
        """Fetch NAV data from database."""
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        qr.fund_id,
                        qr.as_of_date,
                        qr.fund_nav,
                        qr.fund_nav_local,
                        qr.reporting_currency,
                        COUNT(DISTINCT ca.investor_id) as investor_count,
                        SUM(ca.ending_balance) as total_investor_nav
                    FROM pe_quarterly_report qr
                    LEFT JOIN pe_capital_account ca ON 
                        qr.fund_id = ca.fund_id AND 
                        qr.as_of_date = ca.as_of_date
                    WHERE qr.fund_id = :fund_id 
                    AND qr.as_of_date = :as_of_date
                    GROUP BY qr.fund_id, qr.as_of_date, qr.fund_nav, 
                             qr.fund_nav_local, qr.reporting_currency
                """)
                
                result = db.execute(query, {
                    "fund_id": fund_id,
                    "as_of_date": as_of_date
                }).fetchone()
                
                if result:
                    return {
                        "source": "database",
                        "fund_nav": float(result.fund_nav) if result.fund_nav else None,
                        "fund_nav_local": float(result.fund_nav_local) if result.fund_nav_local else None,
                        "reporting_currency": result.reporting_currency,
                        "investor_count": result.investor_count,
                        "total_investor_nav": float(result.total_investor_nav) if result.total_investor_nav else None
                    }
                else:
                    return {"error": "No NAV data found in database"}
                    
        except Exception as e:
            logger.error(f"Error fetching NAV from database: {e}")
            return {"error": str(e)}
    
    async def _fetch_cashflows_from_db(
        self, 
        fund_id: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Fetch cashflow data from database."""
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        as_of_date,
                        SUM(contributions_period) as total_contributions,
                        SUM(distributions_period) as total_distributions,
                        SUM(management_fees_period) as total_mgmt_fees,
                        SUM(other_fees_period) as total_other_fees,
                        COUNT(DISTINCT investor_id) as investor_count
                    FROM pe_capital_account
                    WHERE fund_id = :fund_id
                    AND as_of_date BETWEEN :start_date AND :end_date
                    GROUP BY as_of_date
                    ORDER BY as_of_date
                """)
                
                results = db.execute(query, {
                    "fund_id": fund_id,
                    "start_date": start_date,
                    "end_date": end_date
                }).fetchall()
                
                return [
                    {
                        "date": row.as_of_date.isoformat(),
                        "contributions": float(row.total_contributions or 0),
                        "distributions": float(row.total_distributions or 0),
                        "management_fees": float(row.total_mgmt_fees or 0),
                        "other_fees": float(row.total_other_fees or 0),
                        "net_cashflow": float((row.total_contributions or 0) - 
                                            (row.total_distributions or 0) - 
                                            (row.total_mgmt_fees or 0) - 
                                            (row.total_other_fees or 0))
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error fetching cashflows: {e}")
            return []
    
    async def _fetch_capital_accounts(self, fund_id: str, as_of_date: str) -> List[Dict[str, Any]]:
        """Fetch capital account data."""
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        ca.*,
                        i.name as investor_name
                    FROM pe_capital_account ca
                    JOIN pe_investor i ON ca.investor_id = i.investor_id
                    WHERE ca.fund_id = :fund_id
                    AND ca.as_of_date = :as_of_date
                """)
                
                results = db.execute(query, {
                    "fund_id": fund_id,
                    "as_of_date": as_of_date
                }).fetchall()
                
                return [
                    {
                        "investor_id": row.investor_id,
                        "investor_name": row.investor_name,
                        "beginning_balance": float(row.beginning_balance or 0),
                        "contributions": float(row.contributions_period or 0),
                        "distributions": float(row.distributions_period or 0),
                        "ending_balance": float(row.ending_balance or 0),
                        "total_commitment": float(row.total_commitment or 0),
                        "unfunded_commitment": float(row.unfunded_commitment or 0)
                    }
                    for row in results
                ]
                
        except Exception as e:
            logger.error(f"Error fetching capital accounts: {e}")
            return []
    
    async def _fetch_performance_metrics(self, fund_id: str, as_of_date: str) -> Dict[str, Any]:
        """Fetch performance metrics from database."""
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        net_irr,
                        net_moic,
                        net_dpi,
                        gross_irr,
                        gross_moic,
                        called_percentage,
                        distributed_percentage
                    FROM pe_quarterly_report
                    WHERE fund_id = :fund_id
                    AND as_of_date = :as_of_date
                """)
                
                result = db.execute(query, {
                    "fund_id": fund_id,
                    "as_of_date": as_of_date
                }).fetchone()
                
                if result:
                    return {
                        "net_irr": float(result.net_irr) if result.net_irr else None,
                        "net_moic": float(result.net_moic) if result.net_moic else None,
                        "net_dpi": float(result.net_dpi) if result.net_dpi else None,
                        "gross_irr": float(result.gross_irr) if result.gross_irr else None,
                        "gross_moic": float(result.gross_moic) if result.gross_moic else None,
                        "called_percentage": float(result.called_percentage) if result.called_percentage else None,
                        "distributed_percentage": float(result.distributed_percentage) if result.distributed_percentage else None
                    }
                else:
                    return {"error": "No performance metrics found"}
                    
        except Exception as e:
            logger.error(f"Error fetching performance metrics: {e}")
            return {"error": str(e)}
    
    # Vector store tools
    async def _search_vector_store(self, query: str, fund_id: str = None) -> List[Dict[str, Any]]:
        """Search vector store for relevant documents."""
        try:
            filters = {"fund_id": fund_id} if fund_id else None
            results = await self.vector_store.search(
                query=query,
                top_k=5,
                filters=filters
            )
            
            return [
                {
                    "doc_id": r.get("id"),
                    "content": r.get("text", "")[:500],  # First 500 chars
                    "metadata": r.get("metadata", {}),
                    "score": r.get("score", 0)
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    async def _fetch_document_content(self, doc_id: str) -> Dict[str, Any]:
        """Fetch full document content from vector store."""
        try:
            # Get chunks for the document
            chunks = await self.vector_store.get_chunks(doc_id)
            
            if chunks:
                return {
                    "doc_id": doc_id,
                    "chunks": chunks,
                    "chunk_count": len(chunks)
                }
            else:
                return {"error": "Document not found in vector store"}
                
        except Exception as e:
            logger.error(f"Error fetching document content: {e}")
            return {"error": str(e)}
    
    async def _read_original_file(self, file_path: str) -> Dict[str, Any]:
        """Read and parse original source file."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"error": "File not found"}
            
            if path.suffix.lower() in ['.xlsx', '.xls']:
                # Read Excel file
                df = pd.read_excel(path, sheet_name=None)  # Read all sheets
                return {
                    "file_type": "excel",
                    "sheets": list(df.keys()),
                    "preview": {
                        sheet: df[sheet].head(10).to_dict() 
                        for sheet in list(df.keys())[:2]  # First 2 sheets
                    }
                }
            elif path.suffix.lower() == '.csv':
                # Read CSV file
                df = pd.read_csv(path)
                return {
                    "file_type": "csv",
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "preview": df.head(10).to_dict()
                }
            elif path.suffix.lower() == '.pdf':
                # For PDFs, we'd use PyPDF2 or similar
                return {
                    "file_type": "pdf",
                    "note": "PDF parsing would extract text/tables here"
                }
            else:
                return {"error": f"Unsupported file type: {path.suffix}"}
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return {"error": str(e)}
    
    # Calculation tools
    async def _calculate_irr(self, cashflows: List[Dict[str, Any]]) -> float:
        """Calculate IRR from cashflow series."""
        try:
            # Convert to numpy array of (date, amount) pairs
            cf_list = []
            for cf in cashflows:
                amount = cf.get("net_cashflow", 0)
                if amount != 0:
                    cf_list.append(amount)
            
            if len(cf_list) < 2:
                return 0.0
            
            # Use numpy's IRR calculation
            irr = np.irr(cf_list)
            return float(irr) * 100  # Convert to percentage
            
        except Exception as e:
            logger.error(f"Error calculating IRR: {e}")
            return 0.0
    
    async def _calculate_moic(
        self, 
        total_contributions: float, 
        total_distributions: float, 
        current_nav: float
    ) -> float:
        """Calculate MOIC (Multiple on Invested Capital)."""
        try:
            if total_contributions <= 0:
                return 0.0
            
            total_value = total_distributions + current_nav
            moic = total_value / total_contributions
            
            return round(float(moic), 4)
            
        except Exception as e:
            logger.error(f"Error calculating MOIC: {e}")
            return 0.0
    
    async def _calculate_dpi(
        self, 
        total_distributions: float, 
        total_contributions: float
    ) -> float:
        """Calculate DPI (Distributions to Paid-In)."""
        try:
            if total_contributions <= 0:
                return 0.0
            
            dpi = total_distributions / total_contributions
            return round(float(dpi), 4)
            
        except Exception as e:
            logger.error(f"Error calculating DPI: {e}")
            return 0.0
    
    async def _validate_nav_components(
        self, 
        fund_nav: float, 
        investor_navs: List[float],
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """Validate NAV calculation components."""
        try:
            total_investor_nav = sum(investor_navs)
            variance = abs(fund_nav - total_investor_nav)
            variance_pct = (variance / fund_nav * 100) if fund_nav > 0 else 0
            
            return {
                "fund_nav": fund_nav,
                "sum_of_investor_navs": total_investor_nav,
                "variance": variance,
                "variance_percentage": variance_pct,
                "within_tolerance": variance_pct <= tolerance,
                "investor_count": len(investor_navs)
            }
            
        except Exception as e:
            logger.error(f"Error validating NAV components: {e}")
            return {"error": str(e)}
    
    # Reconciliation tools
    async def _compare_values(
        self,
        value1: float,
        value2: float,
        label1: str = "Source 1",
        label2: str = "Source 2",
        tolerance_pct: float = 0.01
    ) -> Dict[str, Any]:
        """Compare two values and return variance analysis."""
        try:
            variance = abs(value1 - value2)
            avg_value = (value1 + value2) / 2 if (value1 + value2) != 0 else 1
            variance_pct = (variance / avg_value * 100) if avg_value != 0 else 0
            
            return {
                label1: value1,
                label2: value2,
                "variance": variance,
                "variance_percentage": variance_pct,
                "within_tolerance": variance_pct <= tolerance_pct,
                "tolerance_used": tolerance_pct
            }
            
        except Exception as e:
            logger.error(f"Error comparing values: {e}")
            return {"error": str(e)}
    
    async def _flag_discrepancy(
        self,
        discrepancy_type: str,
        description: str,
        severity: str,  # CRITICAL, HIGH, MEDIUM, LOW
        values: Dict[str, Any],
        recommendations: List[str]
    ) -> Dict[str, Any]:
        """Flag a discrepancy with details and recommendations."""
        return {
            "type": discrepancy_type,
            "description": description,
            "severity": severity,
            "values": values,
            "recommendations": recommendations,
            "flagged_at": datetime.utcnow().isoformat()
        }
    
    async def _generate_report(
        self,
        fund_id: str,
        as_of_date: str,
        findings: List[Dict[str, Any]],
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive reconciliation report."""
        
        # Categorize findings by severity
        critical = [f for f in findings if f.get("severity") == "CRITICAL"]
        high = [f for f in findings if f.get("severity") == "HIGH"]
        medium = [f for f in findings if f.get("severity") == "MEDIUM"]
        low = [f for f in findings if f.get("severity") == "LOW"]
        
        return {
            "reconciliation_report": {
                "fund_id": fund_id,
                "as_of_date": as_of_date,
                "generated_at": datetime.utcnow().isoformat(),
                "summary": {
                    "total_findings": len(findings),
                    "critical_issues": len(critical),
                    "high_priority": len(high),
                    "medium_priority": len(medium),
                    "low_priority": len(low),
                    "overall_status": "FAIL" if critical else ("WARNING" if high else "PASS"),
                    **summary
                },
                "findings": {
                    "critical": critical,
                    "high": high,
                    "medium": medium,
                    "low": low
                },
                "recommendations": self._generate_recommendations(findings)
            }
        }
    
    def _generate_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        """Generate prioritized recommendations based on findings."""
        recommendations = []
        
        # Extract all recommendations and deduplicate
        all_recs = []
        for finding in findings:
            all_recs.extend(finding.get("recommendations", []))
        
        # Deduplicate while preserving order
        seen = set()
        for rec in all_recs:
            if rec not in seen:
                recommendations.append(rec)
                seen.add(rec)
        
        return recommendations[:10]  # Top 10 recommendations
    
    async def run_continuous_monitoring(self):
        """Run continuous monitoring for all active funds."""
        
        while True:
            try:
                # Get funds with recent activity
                with get_db_session() as db:
                    query = text("""
                        SELECT DISTINCT f.fund_id, f.fund_name, MAX(ca.as_of_date) as latest_date
                        FROM pe_fund_master f
                        JOIN pe_capital_account ca ON f.fund_id = ca.fund_id
                        WHERE ca.as_of_date >= :cutoff_date
                        GROUP BY f.fund_id, f.fund_name
                    """)
                    
                    cutoff_date = date.today() - timedelta(days=90)
                    funds = db.execute(query, {"cutoff_date": cutoff_date}).fetchall()
                
                logger.info(f"Running reconciliation for {len(funds)} active funds")
                
                for fund in funds:
                    try:
                        result = await self.reconcile_fund(
                            fund_id=fund.fund_id,
                            as_of_date=fund.latest_date
                        )
                        
                        # Store results
                        await self._store_reconciliation_results(
                            fund.fund_id,
                            fund.latest_date,
                            result
                        )
                        
                        # Send alerts if critical issues
                        if result.get("summary", {}).get("critical_issues", 0) > 0:
                            await self._send_critical_alert(fund.fund_id, result)
                        
                    except Exception as e:
                        logger.error(f"Error reconciling fund {fund.fund_id}: {e}")
                
                # Wait before next run (e.g., every hour)
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _store_reconciliation_results(
        self,
        fund_id: str,
        as_of_date: date,
        results: Dict[str, Any]
    ):
        """Store reconciliation results in database."""
        try:
            with get_db_session() as db:
                query = text("""
                    INSERT INTO pe_reconciliation_log (
                        reconciliation_id,
                        fund_id,
                        as_of_date,
                        status,
                        findings_count,
                        critical_count,
                        results_json,
                        created_at
                    ) VALUES (
                        :reconciliation_id,
                        :fund_id,
                        :as_of_date,
                        :status,
                        :findings_count,
                        :critical_count,
                        :results_json,
                        :created_at
                    )
                """)
                
                import uuid
                
                db.execute(query, {
                    "reconciliation_id": str(uuid.uuid4()),
                    "fund_id": fund_id,
                    "as_of_date": as_of_date,
                    "status": results.get("summary", {}).get("overall_status", "ERROR"),
                    "findings_count": results.get("summary", {}).get("total_findings", 0),
                    "critical_count": results.get("summary", {}).get("critical_issues", 0),
                    "results_json": json.dumps(results),
                    "created_at": datetime.utcnow()
                })
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error storing reconciliation results: {e}")
    
    async def _send_critical_alert(self, fund_id: str, results: Dict[str, Any]):
        """Send alert for critical reconciliation issues."""
        # In production, integrate with email/Slack/Teams
        logger.critical(
            f"CRITICAL RECONCILIATION ISSUES - Fund: {fund_id}\n"
            f"Critical Issues: {results.get('summary', {}).get('critical_issues', 0)}\n"
            f"Details: {json.dumps(results.get('findings', {}).get('critical', []), indent=2)}"
        )