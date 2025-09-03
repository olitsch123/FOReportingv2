"""ORM operations for PE documents."""
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.models import Fund, Investor

class PEDataStore:
    """Database operations for PE document data."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def store_nav_observation(self, nav_data: Dict[str, Any]) -> int:
        """
        Store NAV observation with ON CONFLICT upsert.
        Returns nav_obs_id.
        """
        # Prepare data
        fund_id = nav_data.get('fund_id')
        investor_id = nav_data.get('investor_id') 
        as_of_date = nav_data['as_of_date']
        nav_amount = nav_data['nav']
        statement_date = nav_data.get('statement_date', as_of_date)
        coverage_start = nav_data.get('coverage_start')
        coverage_end = nav_data.get('coverage_end', as_of_date)
        scope = nav_data.get('scope', 'FUND')
        scenario = nav_data.get('scenario', 'AS_REPORTED')
        version_no = nav_data.get('version_no', 1)
        doc_id = nav_data.get('doc_id')
        source_trace = nav_data.get('source_trace', {})
        
        # Resolve period_id
        period_id = self._resolve_period_id(as_of_date)
        
        # Insert with ON CONFLICT upsert
        query = text("""
            INSERT INTO pe_nav_observation (
                fund_id, investor_id, scope, nav_amount, as_of_date, statement_date,
                coverage_start, coverage_end, period_id, scenario, version_no,
                restates_nav_obs_id, doc_id, source_trace, created_at
            ) VALUES (
                :fund_id, :investor_id, :scope, :nav_amount, :as_of_date, :statement_date,
                :coverage_start, :coverage_end, :period_id, :scenario, :version_no,
                :restates_nav_obs_id, :doc_id, :source_trace, CURRENT_TIMESTAMP
            )
            ON CONFLICT (fund_id, investor_id, scope, as_of_date, scenario, version_no)
            DO UPDATE SET
                nav_amount = EXCLUDED.nav_amount,
                statement_date = EXCLUDED.statement_date,
                coverage_start = EXCLUDED.coverage_start,
                coverage_end = EXCLUDED.coverage_end,
                period_id = EXCLUDED.period_id,
                doc_id = EXCLUDED.doc_id,
                source_trace = EXCLUDED.source_trace
            RETURNING nav_obs_id
        """)
        
        result = self.db.execute(query, {
            'fund_id': fund_id,
            'investor_id': investor_id,
            'scope': scope,
            'nav_amount': nav_amount,
            'as_of_date': as_of_date,
            'statement_date': statement_date,
            'coverage_start': coverage_start,
            'coverage_end': coverage_end,
            'period_id': period_id,
            'scenario': scenario,
            'version_no': version_no,
            'restates_nav_obs_id': nav_data.get('restates_nav_obs_id'),
            'doc_id': doc_id,
            'source_trace': source_trace
        }).fetchone()
        
        return result[0] if result else None
    
    def store_cashflow(self, cashflow_data: Dict[str, Any]) -> int:
        """
        Store cashflow with ON CONFLICT upsert.
        Returns cashflow_id.
        """
        query = text("""
            INSERT INTO pe_cashflow (
                fund_id, investor_id, flow_type, amount, flow_date, 
                due_date, payment_date, currency, doc_id, source_trace, created_at
            ) VALUES (
                :fund_id, :investor_id, :flow_type, :amount, :flow_date,
                :due_date, :payment_date, :currency, :doc_id, :source_trace, CURRENT_TIMESTAMP
            )
            ON CONFLICT (fund_id, investor_id, flow_type, flow_date, amount)
            DO UPDATE SET
                due_date = EXCLUDED.due_date,
                payment_date = EXCLUDED.payment_date,
                currency = EXCLUDED.currency,
                doc_id = EXCLUDED.doc_id,
                source_trace = EXCLUDED.source_trace
            RETURNING cashflow_id
        """)
        
        result = self.db.execute(query, {
            'fund_id': cashflow_data.get('fund_id'),
            'investor_id': cashflow_data.get('investor_id'),
            'flow_type': cashflow_data['flow_type'],
            'amount': cashflow_data['amount'],
            'flow_date': cashflow_data['flow_date'],
            'due_date': cashflow_data.get('due_date'),
            'payment_date': cashflow_data.get('payment_date'),
            'currency': cashflow_data.get('currency', 'EUR'),
            'doc_id': cashflow_data.get('doc_id'),
            'source_trace': cashflow_data.get('source_trace', {})
        }).fetchone()
        
        return result[0] if result else None
    
    def store_document_metadata(self, doc_data: Dict[str, Any]) -> str:
        """
        Store document metadata.
        Returns doc_id.
        """
        query = text("""
            INSERT INTO pe_document (
                doc_id, org_code, investor_code, doc_type, file_name, file_path,
                file_hash, file_size, fund_id, investor_id, period_end, 
                statement_date, metadata, created_at
            ) VALUES (
                :doc_id, :org_code, :investor_code, :doc_type, :file_name, :file_path,
                :file_hash, :file_size, :fund_id, :investor_id, :period_end,
                :statement_date, :metadata, CURRENT_TIMESTAMP
            )
            ON CONFLICT (file_hash) 
            DO UPDATE SET
                doc_type = EXCLUDED.doc_type,
                fund_id = EXCLUDED.fund_id,
                investor_id = EXCLUDED.investor_id,
                period_end = EXCLUDED.period_end,
                statement_date = EXCLUDED.statement_date,
                metadata = EXCLUDED.metadata
            RETURNING doc_id
        """)
        
        result = self.db.execute(query, doc_data).fetchone()
        return result[0] if result else doc_data.get('doc_id')
    
    def store_page_data(self, page_data: Dict[str, Any]) -> int:
        """Store document page data."""
        query = text("""
            INSERT INTO pe_doc_page (
                doc_id, page_no, text_content, tables_json, bbox, metadata
            ) VALUES (
                :doc_id, :page_no, :text_content, :tables_json, :bbox, :metadata
            )
            ON CONFLICT (doc_id, page_no)
            DO UPDATE SET
                text_content = EXCLUDED.text_content,
                tables_json = EXCLUDED.tables_json,
                bbox = EXCLUDED.bbox,
                metadata = EXCLUDED.metadata
            RETURNING page_id
        """)
        
        result = self.db.execute(query, page_data).fetchone()
        return result[0] if result else None
    
    def get_nav_bridge_view(self, fund_id: str, investor_id: Optional[str] = None, 
                           start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """
        Get monthly NAV bridge data.
        """
        where_clauses = ["n.fund_id = :fund_id"]
        params = {'fund_id': fund_id}
        
        if investor_id:
            where_clauses.append("n.investor_id = :investor_id")
            params['investor_id'] = investor_id
        
        if start_date:
            where_clauses.append("p.period_end >= :start_date")
            params['start_date'] = start_date
            
        if end_date:
            where_clauses.append("p.period_end <= :end_date") 
            params['end_date'] = end_date
        
        where_sql = " AND ".join(where_clauses)
        
        query = text(f"""
            WITH nav_bridge AS (
                SELECT 
                    n.fund_id,
                    n.investor_id,
                    p.period_end,
                    n.nav_amount as nav_end,
                    LAG(n.nav_amount) OVER (
                        PARTITION BY n.fund_id, n.investor_id 
                        ORDER BY p.period_end
                    ) as nav_begin,
                    COALESCE(cf_calls.amount, 0) as contributions,
                    COALESCE(cf_dists.amount, 0) as distributions,
                    COALESCE(cf_fees.amount, 0) as fees,
                    (n.nav_amount - COALESCE(LAG(n.nav_amount) OVER (
                        PARTITION BY n.fund_id, n.investor_id 
                        ORDER BY p.period_end
                    ), 0) - COALESCE(cf_calls.amount, 0) + COALESCE(cf_dists.amount, 0) + COALESCE(cf_fees.amount, 0)) as pnl
                FROM pe_nav_observation n
                JOIN dim_period p ON n.period_id = p.period_id
                LEFT JOIN (
                    SELECT fund_id, investor_id, 
                           DATE_TRUNC('month', flow_date) + INTERVAL '1 month - 1 day' as period_end,
                           SUM(amount) as amount
                    FROM pe_cashflow 
                    WHERE flow_type = 'CALL'
                    GROUP BY fund_id, investor_id, DATE_TRUNC('month', flow_date)
                ) cf_calls ON n.fund_id = cf_calls.fund_id 
                           AND COALESCE(n.investor_id, '') = COALESCE(cf_calls.investor_id, '')
                           AND p.period_end = cf_calls.period_end
                LEFT JOIN (
                    SELECT fund_id, investor_id,
                           DATE_TRUNC('month', flow_date) + INTERVAL '1 month - 1 day' as period_end,
                           SUM(amount) as amount
                    FROM pe_cashflow
                    WHERE flow_type = 'DIST' 
                    GROUP BY fund_id, investor_id, DATE_TRUNC('month', flow_date)
                ) cf_dists ON n.fund_id = cf_dists.fund_id
                            AND COALESCE(n.investor_id, '') = COALESCE(cf_dists.investor_id, '')
                            AND p.period_end = cf_dists.period_end
                LEFT JOIN (
                    SELECT fund_id, investor_id,
                           DATE_TRUNC('month', flow_date) + INTERVAL '1 month - 1 day' as period_end,
                           SUM(amount) as amount
                    FROM pe_cashflow
                    WHERE flow_type = 'FEE'
                    GROUP BY fund_id, investor_id, DATE_TRUNC('month', flow_date)
                ) cf_fees ON n.fund_id = cf_fees.fund_id
                           AND COALESCE(n.investor_id, '') = COALESCE(cf_fees.investor_id, '')
                           AND p.period_end = cf_fees.period_end
                WHERE {where_sql}
            )
            SELECT * FROM nav_bridge
            ORDER BY period_end
        """)
        
        result = self.db.execute(query, params).fetchall()
        
        # Convert to list of dicts
        columns = ['fund_id', 'investor_id', 'period_end', 'nav_end', 'nav_begin', 
                  'contributions', 'distributions', 'fees', 'pnl']
        
        return [dict(zip(columns, row)) for row in result]
    
    def _resolve_period_id(self, as_of_date: date) -> int:
        """Resolve period_id for month-end of as_of_date."""
        import calendar
        
        # Get month-end
        last_day = calendar.monthrange(as_of_date.year, as_of_date.month)[1]
        month_end = date(as_of_date.year, as_of_date.month, last_day)
        
        # Get or create period
        result = self.db.execute(
            text("SELECT period_id FROM dim_period WHERE period_end = :period_end"),
            {'period_end': month_end}
        ).fetchone()
        
        if result:
            return result[0]
        
        # Create new period
        quarter = (month_end.month - 1) // 3 + 1
        self.db.execute(
            text("""
                INSERT INTO dim_period (period_end, year, month, quarter)
                VALUES (:period_end, :year, :month, :quarter)
                ON CONFLICT DO NOTHING
            """),
            {
                'period_end': month_end,
                'year': month_end.year, 
                'month': month_end.month,
                'quarter': quarter
            }
        )
        
        # Get the period_id
        result = self.db.execute(
            text("SELECT period_id FROM dim_period WHERE period_end = :period_end"),
            {'period_end': month_end}
        ).fetchone()
        
        return result[0] if result else None

def create_pe_data_store(db: Session) -> PEDataStore:
    """Create PE data store instance."""
    return PEDataStore(db)