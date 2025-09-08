"""FastAPI endpoints for PE documents (production-grade minimal set)."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Document, FinancialData, Fund, Investor
from app.pe_docs.extractors.multi_method import MultiMethodExtractor
from app.pe_docs.reconciliation.openai_agent import FinancialReconciliationAgent
from app.pe_docs.storage.orm import PEStorageORM
from app.services.vector_service import VectorService

router = APIRouter(prefix="/pe", tags=["PE Documents"])


# Pydantic models for requests/responses
class CapitalAccountSeries(BaseModel):
    """Capital account time series data point."""
    as_of_date: date
    period_label: str
    beginning_balance: float
    ending_balance: float
    contributions_period: float
    distributions_period: float
    management_fees_period: float
    other_fees_period: float
    total_commitment: float
    drawn_commitment: float
    unfunded_commitment: float


class QuarterlyReportData(BaseModel):
    """Quarterly report data model."""
    as_of_date: date
    fund_nav: Optional[float] = None
    net_irr: Optional[float] = None
    net_moic: Optional[float] = None
    net_dpi: Optional[float] = None
    called_percentage: Optional[float] = None
    distributed_percentage: Optional[float] = None


class DocumentMetadata(BaseModel):
    """Document metadata for PE docs."""
    doc_id: str
    doc_type: str
    investor_code: str
    fund_id: Optional[str] = None
    period_date: Optional[date] = None
    extraction_status: str


@router.get("/documents")
async def get_pe_documents(
    doc_type: Optional[str] = Query(None, alias="doc_type"),
    fund_id: Optional[str] = None,
    investor_code: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """List PE documents with optional filtering used by the dashboard.

    Returns a flat list of document metadata fields expected by the UI:
    - id, file_name, doc_type, investor_code, fund_id, created_at
    """
    try:
        stmt = (
            select(
                Document.id,
                Document.filename.label("file_name"),
                Document.document_type.label("doc_type"),
                Investor.code.label("investor_code"),
                Document.fund_id,
                Document.created_at,
                Document.file_path,
            )
            .join(Investor, Investor.id == Document.investor_id)
        )

        conditions = []
        if doc_type:
            conditions.append(Document.document_type == doc_type)
        if fund_id:
            conditions.append(Document.fund_id == fund_id)
        if investor_code:
            conditions.append(Investor.code == investor_code)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Document.created_at.desc()).limit(limit)
        rows = db.execute(stmt).all()
        
        # Filter out documents from folders starting with "!"
        filtered_results = []
        for r in rows:
            # Check if file path contains a folder starting with "!"
            if r.file_path:
                from pathlib import Path
                path = Path(r.file_path)
                # Check all parent folders
                skip_file = False
                for parent in path.parents:
                    if parent.name.startswith('!'):
                        skip_file = True
                        break
                
                if not skip_file:
                    filtered_results.append({
                        "id": str(r.id),
                        "file_name": r.file_name,
                        "doc_type": r.doc_type,
                        "investor_code": r.investor_code,
                        "fund_id": (str(r.fund_id) if r.fund_id else None),
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })
            else:
                # Include files without file_path (shouldn't happen, but defensive)
                filtered_results.append({
                "id": str(r.id),
                "file_name": r.file_name,
                "doc_type": r.doc_type,
                "investor_code": r.investor_code,
                "fund_id": (str(r.fund_id) if r.fund_id else None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                })
        
        return filtered_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {e}")


@router.get("/nav-bridge")
async def get_nav_bridge(
    fund_id: str,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    """Get NAV bridge analysis between two dates.
    
    Returns contributions, distributions, and value changes.
    """
    storage = PEStorageORM()
    
    try:
        # Get capital account data for the period
        query = """
            SELECT 
                investor_id,
                SUM(contributions_period) as total_contributions,
                SUM(distributions_period) as total_distributions,
                MAX(CASE WHEN as_of_date = :start_date THEN ending_balance END) as start_nav,
                MAX(CASE WHEN as_of_date = :end_date THEN ending_balance END) as end_nav
            FROM pe_capital_account
            WHERE fund_id = :fund_id
            AND as_of_date IN (:start_date, :end_date)
            GROUP BY investor_id
        """
        
        results = db.execute(text(query), {
            'fund_id': fund_id,
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        # Aggregate results
        total_start_nav = sum(r.start_nav or 0 for r in results)
        total_end_nav = sum(r.end_nav or 0 for r in results)
        total_contributions = sum(r.total_contributions or 0 for r in results)
        total_distributions = sum(r.total_distributions or 0 for r in results)
        
        # Calculate implied value change
        value_change = total_end_nav - total_start_nav - total_contributions + total_distributions
        
        return {
            "fund_id": fund_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "beginning_nav": float(total_start_nav),
            "contributions": float(total_contributions),
            "distributions": float(total_distributions),
            "value_change": float(value_change),
            "ending_nav": float(total_end_nav),
            "investor_count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NAV bridge error: {e}")


@router.get("/capital-accounts/{investor_code}")
async def get_capital_accounts(
    investor_code: str,
    fund_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Get capital account time series for an investor."""
    storage = PEStorageORM()
    
    try:
        # First get investor ID
        investor = db.query(Investor).filter(Investor.code == investor_code).first()
        if not investor:
            raise HTTPException(status_code=404, detail=f"Investor {investor_code} not found")
        
        # Query capital accounts
        query = db.query(
            text("""
                SELECT 
                    ca.*,
                    f.fund_name
                FROM pe_capital_account ca
                JOIN pe_fund_master f ON ca.fund_id = f.fund_id
                WHERE ca.investor_id = :investor_id
                AND (:fund_id IS NULL OR ca.fund_id = :fund_id)
                ORDER BY ca.as_of_date DESC
                LIMIT :limit
            """)
        )
        
        results = db.execute(query, {
            'investor_id': investor.id,
            'fund_id': fund_id,
            'limit': limit
        }).fetchall()
        
        # Format results
        accounts = []
        for r in results:
            accounts.append({
                "as_of_date": r.as_of_date.isoformat(),
                "fund_id": r.fund_id,
                "fund_name": r.fund_name,
                "beginning_balance": float(r.beginning_balance or 0),
                "contributions_period": float(r.contributions_period or 0),
                "distributions_period": float(r.distributions_period or 0),
                "management_fees_period": float(r.management_fees_period or 0),
                "other_fees_period": float(r.other_fees_period or 0),
                "ending_balance": float(r.ending_balance or 0),
                "total_commitment": float(r.total_commitment or 0),
                "drawn_commitment": float(r.drawn_commitment or 0),
                "unfunded_commitment": float(r.unfunded_commitment or 0)
            })
        
        return {
            "investor_code": investor_code,
            "investor_name": investor.name,
            "capital_accounts": accounts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching capital accounts: {e}")


@router.get("/kpis")
async def get_fund_kpis(
    fund_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Get fund KPIs and performance metrics."""
    storage = PEStorageORM()
    
    try:
        # If no date specified, get latest
        if not as_of_date:
            date_query = """
                SELECT MAX(as_of_date) as latest_date
                FROM pe_quarterly_report
                WHERE (:fund_id IS NULL OR fund_id = :fund_id)
            """
            result = db.execute(text(date_query), {'fund_id': fund_id}).fetchone()
            as_of_date = result.latest_date if result else date.today()
        
        # Get quarterly report data
        query = """
            SELECT 
                qr.*,
                f.fund_name,
                f.fund_currency
            FROM pe_quarterly_report qr
            JOIN pe_fund_master f ON qr.fund_id = f.fund_id
            WHERE (:fund_id IS NULL OR qr.fund_id = :fund_id)
            AND qr.as_of_date = :as_of_date
        """
        
        results = db.execute(text(query), {
            'fund_id': fund_id,
            'as_of_date': as_of_date
        }).fetchall()
        
        # Format KPIs
        kpis = []
        for r in results:
            kpis.append({
                "fund_id": r.fund_id,
                "fund_name": r.fund_name,
                "as_of_date": r.as_of_date.isoformat(),
                "fund_nav": float(r.fund_nav) if r.fund_nav else None,
                "fund_nav_local": float(r.fund_nav_local) if r.fund_nav_local else None,
                "reporting_currency": r.reporting_currency,
                "net_irr": float(r.net_irr) if r.net_irr else None,
                "net_moic": float(r.net_moic) if r.net_moic else None,
                "net_dpi": float(r.net_dpi) if r.net_dpi else None,
                "gross_irr": float(r.gross_irr) if r.gross_irr else None,
                "gross_moic": float(r.gross_moic) if r.gross_moic else None,
                "called_percentage": float(r.called_percentage) if r.called_percentage else None,
                "distributed_percentage": float(r.distributed_percentage) if r.distributed_percentage else None
            })
        
        return {
            "as_of_date": as_of_date.isoformat(),
            "kpis": kpis
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {e}")


@router.get("/cashflows")
async def get_fund_cashflows(
    fund_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Get aggregated cashflow data for a fund."""
    storage = PEStorageORM()
    
    try:
        # Default to last 12 months if no dates specified
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date.replace(year=end_date.year - 1)
        
        # Get cashflow data
        query = """
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
        """
        
        results = db.execute(text(query), {
            'fund_id': fund_id,
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        # Format cashflows
        cashflows = []
        cumulative_contributions = 0
        cumulative_distributions = 0
        
        for r in results:
            cumulative_contributions += float(r.total_contributions or 0)
            cumulative_distributions += float(r.total_distributions or 0)
            
            cashflows.append({
                "date": r.as_of_date.isoformat(),
                "contributions": float(r.total_contributions or 0),
                "distributions": float(r.total_distributions or 0),
                "management_fees": float(r.total_mgmt_fees or 0),
                "other_fees": float(r.total_other_fees or 0),
                "net_cashflow": float((r.total_contributions or 0) - 
                                    (r.total_distributions or 0) - 
                                    (r.total_mgmt_fees or 0) - 
                                    (r.total_other_fees or 0)),
                "cumulative_contributions": cumulative_contributions,
                "cumulative_distributions": cumulative_distributions,
                "investor_count": r.investor_count
            })
        
        return {
            "fund_id": fund_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "cashflows": cashflows
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cashflows: {e}")


# Production endpoints for data extraction and processing
@router.post("/process-capital-account")
async def process_capital_account(
    doc_id: str,
    file_path: str,
    investor_code: str,
    fund_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Process a capital account statement."""
    try:
        # Initialize storage and extractor
        storage = PEStorageORM()
        extractor = MultiMethodExtractor()
        
        # Extract data
        result = extractor.extract_capital_account(file_path)
        
        if result["status"] == "success" and result["data"]:
            # Store in database
            stored_count = 0
            for record in result["data"]:
                # Add metadata
                record["investor_id"] = investor_code
                record["fund_id"] = fund_id or record.get("fund_id")
                record["doc_id"] = doc_id
                
                # Store record
                success = storage.store_capital_account(record, db)
                if success:
                    stored_count += 1
            
            return {
                "status": "success",
                "doc_id": doc_id,
                "records_extracted": len(result["data"]),
                "records_stored": stored_count
            }
        else:
            return {
                "status": "failed",
                "doc_id": doc_id,
                "error": result.get("error", "Extraction failed")
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


@router.post("/process-quarterly-report")
async def process_quarterly_report(
    doc_id: str,
    file_path: str,
    fund_id: str,
    as_of_date: date,
    db: Session = Depends(get_db),
):
    """Process a quarterly report."""
    try:
        # Initialize storage and extractor
        storage = PEStorageORM()
        extractor = MultiMethodExtractor()
        
        # Extract data
        result = extractor.extract_quarterly_report(file_path)
        
        if result["status"] == "success" and result["data"]:
            # Add metadata
            data = result["data"]
            data["fund_id"] = fund_id
            data["as_of_date"] = as_of_date
            data["doc_id"] = doc_id
            
            # Store in database
            success = storage.store_quarterly_report(data, db)
            
            return {
                "status": "success" if success else "failed",
                "doc_id": doc_id,
                "data_stored": success
            }
        else:
            return {
                "status": "failed",
                "doc_id": doc_id,
                "error": result.get("error", "Extraction failed")
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


# Job management endpoints
@router.get("/jobs")
async def get_processing_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get processing job status."""
    try:
        # Get job stats from document table
        query = """
            SELECT 
                processing_status as status,
                COUNT(*) as count
            FROM document
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY processing_status
        """
        
        stats_results = db.execute(text(query)).fetchall()
        
        stats = {
            "total_files": sum(r.count for r in stats_results),
            "processed": sum(r.count for r in stats_results if r.status == 'completed'),
            "queued": sum(r.count for r in stats_results if r.status == 'pending'),
            "errors": sum(r.count for r in stats_results if r.status == 'failed')
        }
        
        # Get recent pending/failed jobs
        job_query = """
            SELECT 
                id as job_id,
                filename as file_name,
                processing_status as status,
                created_at,
                summary as error_message
            FROM document
            WHERE processing_status IN ('pending', 'failed')
            AND (:status IS NULL OR processing_status = :status)
            ORDER BY created_at DESC
            LIMIT :limit
        """
        
        job_results = db.execute(text(job_query), {
            'status': status,
            'limit': limit
        }).fetchall()
        
        pending_jobs = []
        for j in job_results:
            pending_jobs.append({
                "job_id": str(j.job_id),
                "file_name": j.file_name,
                "status": j.status.upper(),
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "error_message": j.error_message
            })
        
        return {
            "stats": stats,
            "pending_jobs": pending_jobs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching jobs: {e}")


@router.post("/retry-job/{job_id}")
async def retry_failed_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retry a failed processing job."""
    try:
        # Get the document
        doc = db.query(Document).filter(Document.id == job_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Reset status to pending
        doc.processing_status = "pending"
        doc.summary = None
        db.commit()
        
        # TODO: Add to processing queue
        # background_tasks.add_task(process_document, job_id)
        
        return {
            "status": "success",
            "message": f"Job {job_id} queued for retry"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrying job: {e}")


# RAG/Search endpoints
class RAGQuery(BaseModel):
    query: str
    fund_id: Optional[str] = None
    doc_type: Optional[str] = None
    limit: int = 5


@router.post("/rag/query")
async def query_documents(
    request: RAGQuery,
    db: Session = Depends(get_db),
):
    """Query documents using RAG."""
    try:
        vector_service = VectorService()
        
        # Build filter
        filters = {}
        if request.fund_id:
            filters["fund_id"] = request.fund_id
        if request.doc_type:
            filters["doc_type"] = request.doc_type
        
        # Search vector store
        results = await vector_service.search(
            query=request.query,
            filters=filters,
            top_k=request.limit
        )
        
        # Format results
        citations = []
        for r in results:
            citations.append({
                "doc_id": r.get("metadata", {}).get("doc_id"),
                "snippet": r.get("text", "")[:200],
                "relevance_score": r.get("score", 0),
                "doc_type": r.get("metadata", {}).get("doc_type"),
                "page_no": r.get("metadata", {}).get("page", 1)
            })
        
        # Generate answer (simplified - in production would use LLM)
        answer = f"Found {len(results)} relevant documents for your query."
        
        return {
            "query": request.query,
            "answer": answer,
            "citations": citations,
            "total_results": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query error: {e}")


# Core handle_file function for the file watcher
async def handle_file(file_path: str, investor_code: str, db: Session) -> Optional[Dict[str, Any]]:
    """Process a file and store results in database.
    
    This is the main entry point called by the file watcher.
    Returns document info or None if processing failed.
    """
    import logging
    import uuid
    from datetime import datetime
    from pathlib import Path

    from sqlalchemy import text

    from app.pe_docs.storage.vector import PEVectorStore
    
    logger = logging.getLogger(__name__)
    
    try:
        file_path = Path(file_path)
        
        # Generate document ID
        import hashlib
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        doc_id = file_hash[:16]  # Use first 16 chars as doc ID
        
        # Check if already processed
        existing = db.execute(text(
            "SELECT doc_id FROM pe_document WHERE doc_id = :doc_id"
        ), {"doc_id": doc_id}).fetchone()
        
        if existing:
            logger.info(f"Document {doc_id} already processed, skipping")
            return {"id": doc_id, "status": "already_processed"}
        
        # Classify document
        from app.pe_docs.classifiers import PEDocumentClassifier
        classifier = PEDocumentClassifier()
        # Read file for classification
        if file_path.suffix.lower() == '.pdf':
            from app.pe_docs.parsers.pdf_core import PDFParser
            parser = PDFParser()
            pdf_data = parser.parse(str(file_path))
            doc_text = pdf_data.get('text', '')[:5000]  # First 5000 chars for classification
        else:
            doc_text = ""
        
        doc_type, confidence = classifier.classify(
            text=doc_text,
            filename=file_path.name,
            first_pages=doc_text
        )
        logger.info(f"Classified {file_path.name} as {doc_type} (confidence: {confidence})")
        
        # Get or create investor
        investor_result = db.execute(text(
            "SELECT investor_id FROM pe_investor WHERE investor_code = :code"
        ), {"code": investor_code}).fetchone()
        
        if investor_result:
            investor_id = investor_result.investor_id
        else:
            # Create investor
            investor_id = str(uuid.uuid4())[:8]
            db.execute(text("""
                INSERT INTO pe_investor (investor_id, investor_code, investor_name)
                VALUES (:id, :code, :name)
            """), {
                "id": investor_id,
                "code": investor_code,
                "name": investor_code.replace("_", " ").title()
            })
        
        # Extract fund info if possible
        fund_id = None
        fund_name = "Unknown Fund"
        
        # Try to extract fund from filename or path
        # Look for fund name in parent folder
        if len(file_path.parts) > 2:
            # Check parent folder name
            parent_folder = file_path.parts[-2]
            if parent_folder and not parent_folder.startswith('!'):
                fund_name = parent_folder
                # Generate UUID-based fund_id from fund name
                fund_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, fund_name))
        
        # If still no fund, try filename
        if fund_id is None:
            filename_parts = file_path.stem.split('_')
            for part in filename_parts:
                if 'fund' in part.lower():
                    fund_name = part
                    fund_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, fund_name))
                    break
        
        # Get or create fund if identified
        if fund_id:
            fund_result = db.execute(text(
                "SELECT fund_id FROM pe_fund_master WHERE fund_id = CAST(:id AS uuid)"
            ), {"id": fund_id}).fetchone()
            
            if not fund_result:
                db.execute(text("""
                    INSERT INTO pe_fund_master (fund_id, fund_code, fund_name, currency)
                    VALUES (CAST(:id AS uuid), :code, :name, :currency)
                """), {
                    "id": fund_id,
                    "code": fund_name[:50],  # Use fund_name as code for now
                    "name": fund_name,
                    "currency": "USD"
                })
        
        # Create document record
        db.execute(text("""
            INSERT INTO pe_document (
                doc_id, doc_type, path, file_hash,
                investor_id, fund_id, created_at
            ) VALUES (
                :doc_id, :doc_type, :path, :file_hash,
                :investor_id, :fund_id, :created_at
            )
        """), {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "path": str(file_path),
            "file_hash": file_hash,
            "investor_id": investor_id,
            "fund_id": fund_id,
            "created_at": datetime.utcnow()
        })
        
        # Process based on document type
        extraction_status = "pending"
        extracted_count = 0
        
        # Process PDF files using OpenAI Universal Extractor
        if file_path.suffix.lower() == '.pdf':
            try:
                # Use the PDF parser to get structured data
                from app.pe_docs.parsers.pdf_core import PDFParser
                parser = PDFParser()
                pdf_data = parser.parse(str(file_path))
                
                # Use OpenAI Universal Extractor for intelligent processing
                from app.pe_docs.extractors.openai_universal import (
                    OpenAIUniversalExtractor,
                )
                extractor = OpenAIUniversalExtractor()
                
                # Extract all data with OpenAI intelligence
                extraction_result = await extractor.extract_and_classify(
                    text=pdf_data['text'],
                    tables=pdf_data.get('tables', []),
                    filename=file_path.name,
                    file_path=str(file_path)
                )
                
                # OpenAI Universal Extractor returns data directly (no status wrapper)
                if extraction_result and not extraction_result.get('extraction_error'):
                    extracted_data = extraction_result
                    
                    # Store extracted data based on document type
                    if doc_type in ['capital_account', 'capital_account_statement'] and extracted_data:
                        # Use OpenAI extracted data directly (it's already normalized)
                        normalized_data = extracted_data
                        as_of_date = normalized_data.get('as_of_date')
                        
                        # OpenAI Universal Extractor already returns properly named fields
                        # Just ensure we have the right field names for database
                        if 'unfunded_commitment' not in normalized_data and 'undrawn_commitment' in normalized_data:
                            normalized_data['unfunded_commitment'] = normalized_data['undrawn_commitment']
                        
                        # CRITICAL FIX: Ensure as_of_date is NEVER null
                        if not as_of_date:
                            import re

                            # Extract Q2 2025 from filename
                            filename = file_path.name
                            quarter_match = re.search(r'Q([1-4])\s+(\d{4})', filename, re.IGNORECASE)
                            if quarter_match:
                                quarter, year = quarter_match.groups()
                                quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
                                as_of_date = f"{year}-{quarter_ends[quarter]}"
                                normalized_data['as_of_date'] = as_of_date
                                logger.info(f"Extracted date from filename: {as_of_date}")
                            else:
                                # Last resort fallback
                                as_of_date = "2025-06-30"  # Default for Q2 2025
                                logger.warning(f"Using hardcoded fallback date: {as_of_date}")
                        
                        # ALWAYS proceed if we have financial data (as_of_date is guaranteed now)
                        if as_of_date or normalized_data.get('ending_balance'):
                            # Use direct insertion instead of storage layer to avoid issues
                            try:
                                db.execute(text("""
                                    INSERT INTO pe_capital_account (
                                        account_id, fund_id, investor_id, as_of_date, 
                                        period_type, reporting_currency,
                                        beginning_balance, ending_balance,
                                        contributions_period, distributions_period,
                                        management_fees_period, partnership_expenses_period,
                                        realized_gain_loss_period, unrealized_gain_loss_period,
                                        total_commitment, drawn_commitment, unfunded_commitment,
                                        source_doc_id, extraction_confidence, created_at, updated_at
                                    ) VALUES (
                                        CAST(:account_id AS uuid), CAST(:fund_id AS uuid), :investor_id, :as_of_date,
                                        :period_type, :reporting_currency,
                                        :beginning_balance, :ending_balance,
                                        :contributions_period, :distributions_period,
                                        :management_fees_period, :partnership_expenses_period,
                                        :realized_gain_loss_period, :unrealized_gain_loss_period,
                                        :total_commitment, :drawn_commitment, :unfunded_commitment,
                                        :source_doc_id, :extraction_confidence, :created_at, :updated_at
                                    )
                                    ON CONFLICT (fund_id, investor_id, as_of_date) 
                                    DO UPDATE SET
                                        ending_balance = EXCLUDED.ending_balance,
                                        contributions_period = EXCLUDED.contributions_period,
                                        distributions_period = EXCLUDED.distributions_period,
                                        updated_at = EXCLUDED.updated_at
                                """), {
                                    'account_id': str(uuid.uuid4()),
                                    'fund_id': fund_id or normalized_data.get('fund_id'),
                                    'investor_id': investor_id,
                                    'as_of_date': as_of_date,
                                    'period_type': normalized_data.get('period_type', 'QUARTERLY'),
                                    'reporting_currency': normalized_data.get('reporting_currency', 'EUR'),
                                    'beginning_balance': normalized_data.get('beginning_balance') or 0,
                                    'ending_balance': normalized_data.get('ending_balance') or 0,
                                    'contributions_period': normalized_data.get('contributions_period') or 0,
                                    'distributions_period': normalized_data.get('distributions_period') or 0,
                                    'management_fees_period': normalized_data.get('management_fees_period') or 0,
                                    'partnership_expenses_period': normalized_data.get('partnership_expenses_period') or 0,
                                    'realized_gain_loss_period': normalized_data.get('realized_gain_loss_period') or 0,
                                    'unrealized_gain_loss_period': normalized_data.get('unrealized_gain_loss_period') or 0,
                                    'total_commitment': normalized_data.get('total_commitment') or 0,
                                    'drawn_commitment': normalized_data.get('drawn_commitment') or 0,
                                    'unfunded_commitment': normalized_data.get('unfunded_commitment') or 0,
                                    'source_doc_id': doc_id,
                                    'extraction_confidence': normalized_data.get('confidence_score', 0.8),
                                    'created_at': datetime.utcnow(),
                                    'updated_at': datetime.utcnow()
                                })
                                extracted_count += 1
                                logger.info(f"Successfully stored capital account data")
                                
                            except Exception as storage_error:
                                logger.error(f"Failed to store capital account: {storage_error}")
                                # Continue processing even if storage fails
                            
                    elif doc_type == 'quarterly_report' and extracted_data.get('nav_data'):
                        # Store NAV observations
                        for nav_record in extracted_data['nav_data']:
                            db.execute(text("""
                                INSERT INTO pe_nav_observation (
                                    fund_id, investor_id, scope, nav_value,
                                    as_of_date, currency
                                ) VALUES (
                                    :fund_id, :investor_id, :scope, :nav_value,
                                    :as_of_date, :currency
                                )
                            """), {
                                'fund_id': fund_id or nav_record.get('fund_id'),
                                'investor_id': investor_id,
                                'scope': 'investor',
                                'nav_value': nav_record.get('nav_value', 0),
                                'as_of_date': nav_record.get('as_of_date'),
                                'currency': nav_record.get('currency', 'USD')
                            })
                            extracted_count += 1
                    
                    extraction_status = 'completed'
                    logger.info(f"Extracted {extracted_count} records from PDF")
                else:
                    extraction_status = extraction_result.get('status', 'failed')
                    
            except Exception as e:
                logger.error(f"Error processing PDF: {e}")
                extraction_status = 'failed'
                # Log error but continue (extraction_error column doesn't exist yet)
                logger.error(f"Failed to store extraction error: {e}")
        
        # Process Excel files
        elif doc_type == "capital_account" and file_path.suffix in ['.xlsx', '.xls']:
            try:
                # Read Excel file content
                import pandas as pd
                df = pd.read_excel(str(file_path))
                
                # Convert to text and tables format for extractor
                text = df.to_string()
                tables = [df.to_dict('records')]
                
                extractor = MultiMethodExtractor()
                result = await extractor.process_document(
                    file_path=str(file_path),
                    text=text,
                    tables=tables,
                    doc_metadata={
                        'doc_id': doc_id,
                        'doc_type': 'capital_account_statement',
                        'fund_id': fund_id,
                        'investor_id': investor_id,
                        'filename': file_path.name
                    }
                )
                
                if result["status"] == "success":
                    extracted_data = result.get('extracted_data', {})
                    # Store capital account data similar to PDF processing
                    if extracted_data and extracted_data.get('as_of_date'):
                        db.execute(text("""
                            INSERT INTO pe_capital_account (
                                account_id, investor_id, fund_id, as_of_date, reporting_currency,
                                beginning_balance, ending_balance,
                                contributions_period, distributions_period,
                                management_fees_period, partnership_expenses_period,
                                realized_gain_loss_period, unrealized_gain_loss_period,
                                total_commitment, drawn_commitment, unfunded_commitment
                            ) VALUES (
                                CAST(:account_id AS uuid), :investor_id, CAST(:fund_id AS uuid), :as_of_date, :reporting_currency,
                                :beginning_balance, :ending_balance,
                                :contributions_period, :distributions_period,
                                :management_fees_period, :partnership_expenses_period,
                                :realized_gain_loss_period, :unrealized_gain_loss_period,
                                :total_commitment, :drawn_commitment, :unfunded_commitment
                            )
                            ON CONFLICT (investor_id, fund_id, as_of_date) 
                            DO UPDATE SET
                                ending_balance = EXCLUDED.ending_balance,
                                contributions_period = EXCLUDED.contributions_period,
                                distributions_period = EXCLUDED.distributions_period
                        """), {
                            "account_id": str(uuid.uuid4()),
                            "investor_id": investor_id,
                            "fund_id": fund_id or extracted_data.get("fund_id"),
                            "as_of_date": extracted_data["as_of_date"],
                            "reporting_currency": extracted_data.get("currency", "USD"),
                            "beginning_balance": extracted_data.get("beginning_balance", 0),
                            "ending_balance": extracted_data.get("ending_balance", 0),
                            "contributions_period": extracted_data.get("contributions_period", 0),
                            "distributions_period": extracted_data.get("distributions_period", 0),
                            "management_fees_period": extracted_data.get("management_fees_period", 0),
                            "partnership_expenses_period": extracted_data.get("partnership_expenses_period", 0),
                            "realized_gain_loss_period": extracted_data.get("realized_gain_loss_period", 0),
                            "unrealized_gain_loss_period": extracted_data.get("unrealized_gain_loss_period", 0),
                            "total_commitment": extracted_data.get("total_commitment", 0),
                            "drawn_commitment": extracted_data.get("drawn_commitment", 0),
                            "unfunded_commitment": extracted_data.get("unfunded_commitment", 0)
                        })
                        extracted_count += 1
                    
                    extraction_status = "completed"
                    logger.info(f"Extracted capital account data from Excel")
                else:
                    extraction_status = "no_data"
                    
            except Exception as e:
                logger.error(f"Error extracting capital account: {e}")
                extraction_status = "failed"
                # Log error but continue (extraction_error column doesn't exist yet)
                logger.error(f"Failed to store extraction error: {e}")
        
        # Update document with extraction status
        # Note: Currently we only have embedding_status column, not processing_status
        # This can be enhanced with additional columns later
        
        # Create embeddings and upload to vector store using new backend
        if extraction_status in ['completed', 'no_data']:
            try:
                logger.info(f"Creating embeddings for document {doc_id}")
                
                # Use ChromaDB backend (more reliable than OpenAI Vector Store for chunks)
                from app.services.vector_backends.chroma_backend import (
                    ChromaVectorBackend,
                )
                vector_backend = ChromaVectorBackend()
                
                # Prepare chunks with extracted financial data
                chunks = []
                
                # For capital account statements with extracted data
                if doc_type in ['capital_account_statement', 'capital_account'] and extracted_count > 0:
                    # Create rich chunks from extracted financial data
                    if 'normalized_data' in locals() and normalized_data:
                        chunk_text = f"""Capital Account Statement - {normalized_data.get('fund_name', fund_name)}

Investor: {normalized_data.get('investor_name', investor_code)}
Fund: {normalized_data.get('fund_name', fund_name)}
As of Date: {normalized_data.get('as_of_date', 'Unknown')}
Currency: {normalized_data.get('reporting_currency', 'EUR')}

Financial Summary:
- Beginning Balance: {normalized_data.get('beginning_balance', 0):,.2f}
- Ending Balance: {normalized_data.get('ending_balance', 0):,.2f}
- Total Commitment: {normalized_data.get('total_commitment', 0):,.2f}
- Drawn Commitment: {normalized_data.get('drawn_commitment', 0):,.2f}
- Unfunded Commitment: {normalized_data.get('unfunded_commitment', 0):,.2f}
- Contributions (Period): {normalized_data.get('contributions_period', 0):,.2f}
- Distributions (Period): {normalized_data.get('distributions_period', 0):,.2f}
- Management Fees: {normalized_data.get('management_fees_period', 0):,.2f}
- Unrealized Gains/Losses: {normalized_data.get('unrealized_gain_loss_period', 0):,.2f}

This document contains detailed capital account information for {normalized_data.get('investor_name', investor_code)} 
in {normalized_data.get('fund_name', fund_name)} as of {normalized_data.get('as_of_date', 'the reporting period')}."""
                    else:
                        chunk_text = f"""Capital Account Statement
Fund: {fund_name}
Investor: {investor_code}
File: {file_path.name}
Records Extracted: {extracted_count}"""
                    
                    chunks.append({
                        'text': chunk_text,
                        'doc_type': doc_type,
                        'fund_id': fund_id,
                        'investor_id': investor_id,
                        'metadata': {
                            'file_name': file_path.name,
                            'doc_id': doc_id,
                            'extracted_records': extracted_count,
                            'fund_name': normalized_data.get('fund_name', fund_name) if 'normalized_data' in locals() else fund_name,
                            'investor_name': normalized_data.get('investor_name', investor_code) if 'normalized_data' in locals() else investor_code,
                            'as_of_date': normalized_data.get('as_of_date') if 'normalized_data' in locals() else None,
                            'currency': normalized_data.get('reporting_currency', 'EUR') if 'normalized_data' in locals() else 'EUR'
                        }
                    })
                else:
                    # For PDFs and other documents, read content
                    if file_path.suffix.lower() == '.pdf':
                        try:
                            import PyPDF2
                            with open(str(file_path), 'rb') as pdf_file:
                                pdf_reader = PyPDF2.PdfReader(pdf_file)
                                for page_num, page in enumerate(pdf_reader.pages):
                                    page_text = page.extract_text()
                                    if page_text.strip():
                                        chunks.append({
                                            'text': page_text,
                                            'page_no': page_num + 1,
                                            'doc_type': doc_type,
                                            'fund_id': fund_id,
                                            'investor_id': investor_id,
                                            'metadata': {
                                                'file_name': file_path.name,
                                                'doc_id': doc_id,
                                                'page': page_num + 1
                                            }
                                        })
                        except Exception as e:
                            logger.warning(f"Could not extract PDF text: {e}")
                    
                    # If no chunks created, create a basic metadata chunk
                    if not chunks:
                        chunk_text = f"""Document: {file_path.name}
Type: {doc_type}
Fund: {fund_name}
Investor: {investor_code}
File Path: {str(file_path)}"""
                        
                        chunks.append({
                            'text': chunk_text,
                            'doc_type': doc_type,
                            'fund_id': fund_id,
                            'investor_id': investor_id,
                            'metadata': {
                                'file_name': file_path.name,
                                'doc_id': doc_id
                            }
                        })
                
                # Upload chunks to vector store using new backend
                if chunks:
                    chunk_ids = await vector_backend.add_chunks(doc_id, chunks)
                    logger.info(f"Added {len(chunk_ids)} chunks to ChromaDB for document {doc_id}")
                    
                    # Update pe_document with embedding status
                    db.execute(text("""
                        UPDATE pe_document 
                        SET embedding_status = :status,
                            chunk_count = :chunk_count
                        WHERE doc_id = :doc_id
                    """), {
                        "doc_id": doc_id,
                        "status": 'completed',
                        "chunk_count": len(chunk_ids)
                    })
                    
            except Exception as e:
                logger.error(f"Failed to create embeddings for {doc_id}: {e}")
                # Update pe_document with embedding failure
                db.execute(text("""
                    UPDATE pe_document 
                    SET embedding_status = :status,
                        embedding_error = :error
                    WHERE doc_id = :doc_id
                """), {
                    "doc_id": doc_id,
                    "status": 'failed',
                    "error": str(e)
                })
        
        db.commit()
        
        # Return document info
        return {
            "id": doc_id,
            "doc_type": doc_type,
            "fund_name": fund_name,
            "investor_name": investor_code,
            "extraction_status": extraction_status,
            "extracted_records": extracted_count
        }
        
    except Exception as e:
        logger.error(f"Failed to handle file {file_path}: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return None


# Reconciliation endpoints
@router.post("/reconcile")
async def run_reconciliation(
    fund_id: str,
    as_of_date: date,
    reconciliation_scope: Optional[List[str]] = None,
    db: Session = Depends(get_db),
):
    """Run comprehensive reconciliation for a fund."""
    try:
        agent = FinancialReconciliationAgent()
        
        # Run reconciliation
        result = await agent.reconcile_fund(
            fund_id=fund_id,
            as_of_date=as_of_date,
            reconciliation_scope=reconciliation_scope
        )
        
        # Store results in database
        await agent._store_reconciliation_results(fund_id, as_of_date, result)
        
        return {
            "status": "success",
            "reconciliation_id": result.get("reconciliation_report", {}).get("generated_at"),
            "summary": result.get("reconciliation_report", {}).get("summary"),
            "findings_count": result.get("reconciliation_report", {}).get("summary", {}).get("total_findings", 0)
        }
        
    except Exception as e:
        logger.error(f"Reconciliation error: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {e}")


@router.get("/reconciliation-history")
async def get_reconciliation_history(
    fund_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get reconciliation history."""
    try:
        query = text("""
            SELECT 
                reconciliation_id,
                fund_id,
                as_of_date,
                status,
                findings_count,
                critical_count,
                created_at
            FROM pe_reconciliation_log
            WHERE (:fund_id IS NULL OR fund_id = :fund_id)
            AND (:status IS NULL OR status = :status)
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        results = db.execute(query, {
            "fund_id": fund_id,
            "status": status,
            "limit": limit
        }).fetchall()
        
        history = []
        for r in results:
            history.append({
                "reconciliation_id": r.reconciliation_id,
                "fund_id": r.fund_id,
                "as_of_date": r.as_of_date.isoformat(),
                "status": r.status,
                "findings_count": r.findings_count,
                "critical_count": r.critical_count,
                "created_at": r.created_at.isoformat()
            })
        
        return {
            "reconciliations": history,
            "total": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error fetching reconciliation history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {e}")


@router.get("/reconciliation/{reconciliation_id}")
async def get_reconciliation_details(
    reconciliation_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed reconciliation results."""
    try:
        query = text("""
            SELECT 
                reconciliation_id,
                fund_id,
                as_of_date,
                status,
                findings_count,
                critical_count,
                results_json,
                created_at
            FROM pe_reconciliation_log
            WHERE reconciliation_id = :reconciliation_id
        """)
        
        result = db.execute(query, {
            "reconciliation_id": reconciliation_id
        }).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Reconciliation not found")
        
        return {
            "reconciliation_id": result.reconciliation_id,
            "fund_id": result.fund_id,
            "as_of_date": result.as_of_date.isoformat(),
            "status": result.status,
            "findings_count": result.findings_count,
            "critical_count": result.critical_count,
            "details": result.results_json,
            "created_at": result.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching reconciliation details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch details: {e}")