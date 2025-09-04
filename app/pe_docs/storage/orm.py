"""ORM storage for PE documents data."""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, select
from sqlalchemy.dialects.postgresql import insert
from structlog import get_logger
from app.database.connection import get_db

logger = get_logger()


class PEStorage:
    """Storage manager for PE documents data."""
    
    def __init__(self, db: Session):
        """Initialize storage with database session."""
        self.db = db
    
    def store_document(self, doc_data: Dict[str, Any]) -> str:
        """Store PE document and return doc_id."""
        # Implementation depends on actual PE database models
        # This is a placeholder showing the interface
        
        try:
            # Store in pe_document table
            doc_id = self._store_pe_document(doc_data)
            
            # Store pages
            if 'pages' in doc_data:
                self._store_document_pages(doc_id, doc_data['pages'])
            
            # Store extracted data based on document type
            doc_type = doc_data.get('doc_type')
            if doc_type == 'capital_account_statement':
                self._store_cas_data(doc_id, doc_data)
            elif doc_type in ['quarterly_report', 'annual_report']:
                self._store_nav_observation(doc_id, doc_data)
                self._store_performance_data(doc_id, doc_data)
            elif doc_type in ['capital_call_notice', 'distribution_notice']:
                self._store_cashflow(doc_id, doc_data)
            
            self.db.commit()
            
            logger.info(
                "pe_document_stored",
                doc_id=doc_id,
                doc_type=doc_type
            )
            
            return doc_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "pe_document_storage_failed",
                error=str(e),
                doc_type=doc_data.get('doc_type')
            )
            raise
    
    def _store_pe_document(self, doc_data: Dict[str, Any]) -> str:
        """Store main document record."""
        # Create pe_document record
        # This would use actual SQLAlchemy models
        doc_id = doc_data.get('doc_id')
        
        # INSERT INTO pe_document ...
        
        return doc_id
    
    def _store_document_pages(self, doc_id: str, pages: List[Dict[str, Any]]) -> None:
        """Store document pages."""
        for page in pages:
            # INSERT INTO pe_doc_page ...
            pass
    
    def _store_nav_observation(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Store NAV observation data."""
        # Extract NAV fields
        nav_data = {
            'doc_id': doc_id,
            'fund_id': data.get('fund_id'),
            'investor_id': data.get('investor_id'),
            'as_of_date': data.get('as_of_date'),
            'nav': data.get('nav'),
            'nav_per_share': data.get('nav_per_share'),
            'scope': data.get('scope', 'FUND'),
            'source_trace': {
                'doc_id': doc_id,
                'extraction_method': data.get('extraction_method'),
                'confidence': data.get('confidence_score')
            }
        }
        
        # INSERT INTO pe_nav_observation ...
    
    def _store_cas_data(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Store Capital Account Statement data."""
        # Store as NAV observation
        self._store_nav_observation(doc_id, {
            **data,
            'nav': data.get('ending_balance')
        })
        
        # Store cashflows
        if 'contributions' in data and data['contributions']:
            self._store_cashflow(doc_id, {
                'flow_type': 'CALL',
                'amount': data['contributions'],
                'flow_date': data.get('period_end_date')
            })
        
        if 'distributions' in data and data['distributions']:
            self._store_cashflow(doc_id, {
                'flow_type': 'DIST',
                'amount': data['distributions'],
                'flow_date': data.get('period_end_date')
            })
    
    def _store_cashflow(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Store cashflow record."""
        cashflow_data = {
            'doc_id': doc_id,
            'fund_id': data.get('fund_id'),
            'investor_id': data.get('investor_id'),
            'flow_type': data.get('flow_type'),
            'amount': data.get('amount'),
            'flow_date': data.get('flow_date'),
            'due_date': data.get('due_date'),
            'source_trace': {
                'doc_id': doc_id,
                'extracted_from': data.get('extracted_from')
            }
        }
        
        # INSERT INTO pe_cashflow ...
    
    def _store_performance_data(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Store performance metrics."""
        perf_data = {
            'doc_id': doc_id,
            'fund_id': data.get('fund_id'),
            'as_of_date': data.get('as_of_date'),
            'irr': data.get('irr'),
            'moic': data.get('moic'),
            'dpi': data.get('dpi'),
            'rvpi': data.get('rvpi'),
            'tvpi': data.get('tvpi'),
            'source_trace': {
                'doc_id': doc_id
            }
        }
        
        # INSERT INTO pe_perf_reported ...
    
    def get_nav_observations(self, 
                           fund_id: str,
                           investor_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve NAV observations."""
        # Build query
        # SELECT * FROM pe_nav_observation WHERE ...
        
        observations = []
        
        return observations
    
    def get_latest_nav(self, 
                      fund_id: str,
                      investor_id: Optional[str] = None,
                      as_of_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Get latest NAV observation."""
        # SELECT * FROM pe_nav_observation 
        # WHERE fund_id = ? AND as_of_date <= ?
        # ORDER BY as_of_date DESC LIMIT 1
        
        return None
    
    def get_cashflows(self,
                     fund_id: str,
                     investor_id: Optional[str] = None,
                     flow_type: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Retrieve cashflows."""
        # SELECT * FROM pe_cashflow WHERE ...
        
        cashflows = []
        
        return cashflows
    
    def calculate_nav_bridge(self,
                           fund_id: str,
                           start_date: datetime,
                           end_date: datetime,
                           investor_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculate NAV bridge between dates."""
        # Get beginning NAV
        begin_nav = self.get_latest_nav(fund_id, investor_id, start_date)
        
        # Get ending NAV  
        end_nav = self.get_latest_nav(fund_id, investor_id, end_date)
        
        # Get cashflows in period
        cashflows = self.get_cashflows(
            fund_id, investor_id, 
            start_date=start_date, 
            end_date=end_date
        )
        
        # Calculate bridge components
        contributions = sum(
            cf['amount'] for cf in cashflows 
            if cf['flow_type'] == 'CALL'
        )
        distributions = sum(
            cf['amount'] for cf in cashflows 
            if cf['flow_type'] == 'DIST'
        )
        fees = sum(
            cf['amount'] for cf in cashflows 
            if cf['flow_type'] == 'FEE'
        )
        
        # Calculate P&L
        nav_begin = begin_nav['nav'] if begin_nav else 0
        nav_end = end_nav['nav'] if end_nav else 0
        pnl = nav_end - nav_begin - contributions + distributions + fees
        
        return {
            'fund_id': fund_id,
            'investor_id': investor_id,
            'start_date': start_date,
            'end_date': end_date,
            'nav_begin': nav_begin,
            'contributions': contributions,
            'distributions': distributions,
            'fees': fees,
            'pnl': pnl,
            'nav_end': nav_end
        }


class PEStorageORM:
    """ORM-based storage for PE documents with enhanced functionality."""
    
    def __init__(self):
        """Initialize storage ORM."""
        pass
    
    async def create_extraction_audit(
        self,
        doc_id: str,
        field_name: str,
        extracted_value: str,
        extraction_method: str,
        confidence_score: float,
        validation_status: str,
        validation_errors: List[Dict] = None
    ) -> str:
        """Create extraction audit record."""
        from app.database.connection import get_db_session
        
        audit_id = str(uuid.uuid4())
        
        with get_db_session() as db:
            try:
                # Insert into extraction_audit table
                stmt = """
                    INSERT INTO extraction_audit (
                        audit_id, doc_id, field_name, extracted_value,
                        extraction_method, confidence_score, validation_status,
                        validation_errors, extraction_timestamp
                    ) VALUES (
                        :audit_id, :doc_id, :field_name, :extracted_value,
                        :extraction_method, :confidence_score, :validation_status,
                        :validation_errors, :timestamp
                    )
                """
                
                db.execute(stmt, {
                    'audit_id': audit_id,
                    'doc_id': doc_id,
                    'field_name': field_name,
                    'extracted_value': extracted_value,
                    'extraction_method': extraction_method,
                    'confidence_score': confidence_score,
                    'validation_status': validation_status,
                    'validation_errors': validation_errors,
                    'timestamp': datetime.utcnow()
                })
                
                db.commit()
                
                logger.info(
                    "extraction_audit_created",
                    audit_id=audit_id,
                    doc_id=doc_id,
                    field=field_name
                )
                
                return audit_id
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error creating extraction audit: {e}")
                raise
    
    async def upsert_capital_account(
        self,
        fund_id: str,
        investor_id: str,
        as_of_date: date,
        data: Dict[str, Any]
    ) -> str:
        """Upsert capital account data."""
        from app.database.connection import get_db_session
        
        account_id = str(uuid.uuid4())
        
        with get_db_session() as db:
            try:
                # Prepare data for insertion
                insert_data = {
                    'account_id': account_id,
                    'fund_id': fund_id,
                    'investor_id': investor_id,
                    'as_of_date': as_of_date,
                    'period_type': data.get('period_type', 'QUARTERLY'),
                    'period_label': data.get('period_label'),
                    
                    # Balances
                    'beginning_balance': self._to_decimal(data.get('beginning_balance')),
                    'ending_balance': self._to_decimal(data.get('ending_balance')),
                    
                    # Activity
                    'contributions_period': self._to_decimal(data.get('contributions_period')),
                    'distributions_period': self._to_decimal(data.get('distributions_period')),
                    'distributions_roc_period': self._to_decimal(data.get('distributions_roc_period')),
                    'distributions_gain_period': self._to_decimal(data.get('distributions_gain_period')),
                    'distributions_income_period': self._to_decimal(data.get('distributions_income_period')),
                    
                    # Fees
                    'management_fees_period': self._to_decimal(data.get('management_fees_period')),
                    'partnership_expenses_period': self._to_decimal(data.get('partnership_expenses_period')),
                    
                    # Gains/Losses
                    'realized_gain_loss_period': self._to_decimal(data.get('realized_gain_loss_period')),
                    'unrealized_gain_loss_period': self._to_decimal(data.get('unrealized_gain_loss_period')),
                    
                    # Commitments
                    'total_commitment': self._to_decimal(data.get('total_commitment')),
                    'drawn_commitment': self._to_decimal(data.get('drawn_commitment')),
                    'unfunded_commitment': self._to_decimal(data.get('unfunded_commitment')),
                    
                    # Metadata
                    'source_doc_id': data.get('doc_id'),
                    'extraction_confidence': data.get('overall_confidence', 0.0),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                
                # Use PostgreSQL UPSERT
                stmt = insert(db.tables['pe_capital_account']).values(**insert_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['fund_id', 'investor_id', 'as_of_date'],
                    set_={
                        'ending_balance': stmt.excluded.ending_balance,
                        'updated_at': datetime.utcnow(),
                        # Update other fields as needed
                    }
                )
                
                db.execute(stmt)
                db.commit()
                
                logger.info(
                    "capital_account_upserted",
                    account_id=account_id,
                    fund_id=fund_id,
                    investor_id=investor_id,
                    as_of_date=as_of_date
                )
                
                return account_id
                
            except Exception as e:
                db.rollback()
                logger.error(f"Error upserting capital account: {e}")
                raise
    
    async def get_extraction_by_doc_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get extraction data by document ID."""
        from app.database.connection import get_db_session
        
        with get_db_session() as db:
            try:
                # Query from appropriate table based on doc type
                # This is simplified - in practice would need to check doc type first
                stmt = """
                    SELECT * FROM pe_capital_account
                    WHERE source_doc_id = :doc_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                
                result = db.execute(stmt, {'doc_id': doc_id}).fetchone()
                
                if result:
                    return dict(result)
                
                return None
                
            except Exception as e:
                logger.error(f"Error getting extraction by doc_id: {e}")
                return None
    
    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        """Convert value to Decimal safely."""
        if value is None:
            return None
        
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except:
            return None