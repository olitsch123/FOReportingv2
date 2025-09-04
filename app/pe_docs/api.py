"""FastAPI endpoints for PE documents (production-grade minimal set)."""
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Literal
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, text

from app.database.connection import get_db
from app.database.models import Document, Investor, Fund, FinancialData
from app.services.vector_service import VectorService
from app.pe_docs.storage.orm import PEStorageORM
from app.pe_docs.extractors.multi_method import MultiMethodExtractor


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
    net_activity: float
    nav_change: float
    nav_change_pct: float
    unfunded_commitment: float
    drawn_commitment: float
    contribution_pace: float


class ForecastRequest(BaseModel):
    """Request model for forecasting."""
    scenario: Literal["base", "conservative", "aggressive"] = "base"
    years_forward: int = 5
    
    
class ReconciliationRequest(BaseModel):
    """Request model for reconciliation."""
    as_of_date: date
    reconciliation_types: List[str] = ["nav", "cashflow", "performance", "commitment"]


@router.get("/health")
async def pe_health():
    """PE module health check."""
    return {"status": "healthy", "module": "pe_docs", "version": "2.2"}


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
        return [
            {
                "id": str(r.id),
                "file_name": r.file_name,
                "doc_type": r.doc_type,
                "investor_code": r.investor_code,
                "fund_id": (str(r.fund_id) if r.fund_id else None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {e}")


@router.get("/nav-bridge")
async def get_nav_bridge(
    fund_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return a minimal monthly NAV bridge derived from FinancialData.

    Output structure:
    { "periods": [ { "period_end": "YYYY-MM-DD", "nav_end": number }, ... ] }
    """
    try:
        if not fund_id:
            raise HTTPException(status_code=400, detail="fund_id is required")

        # Date filters
        sd = datetime.fromisoformat(start_date).date() if start_date else None
        ed = datetime.fromisoformat(end_date).date() if end_date else None

        # Convert fund_id string to UUID if needed, handle gracefully
        try:
            import uuid
            fund_uuid = uuid.UUID(fund_id)
        except ValueError:
            # fund_id is not a valid UUID, return empty periods
            return {"periods": []}

        stmt = select(
            func.date_trunc("month", FinancialData.reporting_date).label("period_end"),
            func.max(FinancialData.nav).label("nav_end"),
        ).where(FinancialData.fund_id == fund_uuid)

        if sd:
            stmt = stmt.where(FinancialData.reporting_date >= sd)
        if ed:
            stmt = stmt.where(FinancialData.reporting_date <= ed)

        stmt = stmt.group_by(func.date_trunc("month", FinancialData.reporting_date)).order_by(
            func.date_trunc("month", FinancialData.reporting_date)
        )
        rows = db.execute(stmt).all()

        periods = [
            {
                "period_end": r.period_end.date().isoformat() if hasattr(r.period_end, "date") else str(r.period_end),
                "nav_end": float(r.nav_end) if r.nav_end is not None else 0.0,
            }
            for r in rows
        ]
        return {"periods": periods}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building NAV bridge: {e}")


@router.get("/kpis")
async def get_kpis(
    fund_id: str,
    as_of_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return KPI tiles (TVPI, DPI, RVPI, current NAV) from the latest FinancialData row."""
    try:
        if not fund_id:
            raise HTTPException(status_code=400, detail="fund_id is required")

        ad = datetime.fromisoformat(as_of_date) if as_of_date else datetime.utcnow()
        
        # Convert fund_id string to UUID if needed, handle gracefully
        try:
            import uuid
            fund_uuid = uuid.UUID(fund_id)
        except ValueError:
            # fund_id is not a valid UUID, return empty KPIs
            return {"tvpi": 0.0, "dpi": 0.0, "rvpi": 0.0, "current_nav": 0.0}
        
        stmt = (
            select(FinancialData)
            .where(and_(FinancialData.fund_id == fund_uuid, FinancialData.reporting_date <= ad))
            .order_by(FinancialData.reporting_date.desc())
            .limit(1)
        )
        row = db.execute(stmt).scalar_one_or_none()
        if not row:
            return {"tvpi": 0.0, "dpi": 0.0, "rvpi": 0.0, "current_nav": 0.0}
        return {
            "tvpi": float(row.tvpi or 0.0),
            "dpi": float(row.dpi or 0.0),
            "rvpi": float(row.rvpi or 0.0),
            "current_nav": float(row.nav or 0.0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {e}")


@router.get("/cashflows")
async def get_cashflows(
    fund_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return cashflows for the fund.

    Note: Cashflow table not present; return empty list to keep UI stable.
    """
    try:
        _ = fund_id  # placeholder use
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cashflows: {e}")


@router.get("/jobs")
async def get_jobs(db: Session = Depends(get_db)):
    """Return ingestion/processing job stats derived from Document table."""
    try:
        total = db.execute(select(func.count()).select_from(Document)).scalar() or 0
        processed = (
            db.execute(select(func.count()).select_from(Document).where(Document.processing_status == "completed")).scalar()
            or 0
        )
        queued = (
            db.execute(select(func.count()).select_from(Document).where(Document.processing_status.in_(["pending", "processing"]))).scalar()
            or 0
        )
        errors = (
            db.execute(select(func.count()).select_from(Document).where(Document.processing_status == "failed")).scalar()
            or 0
        )

        # Sample pending jobs (with job_id, file_name, status for frontend)
        pending_rows = db.execute(
            select(Document.id, Document.filename, Document.file_path, Document.processing_status)
            .where(Document.processing_status.in_(["pending", "processing", "failed"]))
            .order_by(Document.created_at.desc())
            .limit(20)
        ).all()
        pending_jobs = [
            {
                "job_id": str(r.id),
                "file_name": r.filename,
                "file_path": r.file_path,
                "status": r.processing_status.upper()  # frontend expects uppercase
            }
            for r in pending_rows
        ]

        return {"stats": {"total_files": total, "processed": processed, "queued": queued, "errors": errors}, "pending_jobs": pending_jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching jobs: {e}")


@router.post("/retry-job/{job_id}")
async def retry_job(job_id: str, db: Session = Depends(get_db)):
    """Retry a failed processing job by resetting its status to pending."""
    try:
        # Find document by ID and reset processing status
        stmt = select(Document).where(Document.id == job_id)
        doc = db.execute(stmt).scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if doc.processing_status != "failed":
            raise HTTPException(status_code=400, detail="Only failed jobs can be retried")
        
        # Reset to pending
        doc.processing_status = "pending"
        doc.processing_error = None
        doc.processed_at = None
        
        db.commit()
        
        return {"success": True, "message": "Job queued for retry", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error retrying job: {e}")


@router.post("/rag/query")
async def rag_query(
    query_data: Dict[str, Any],
    db: Session = Depends(get_db),  # kept for future use
):
    """Vector search over document chunks with optional metadata filters.

    Request JSON: { query: str, top_k?: int, fund_id?: str, doc_type?: str }
    Response JSON: { answer: str, citations: [ { doc_id, snippet, doc_type, relevance_score, page_no? } ] }
    """
    try:
        query = (query_data or {}).get("query", "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        top_k = int((query_data or {}).get("top_k", 5))
        filter_md: Dict[str, Any] = {}
        if query_data.get("fund_id"):
            filter_md["fund_id"] = query_data["fund_id"]
        if query_data.get("doc_type"):
            filter_md["document_type"] = query_data["doc_type"]

        vector = VectorService()
        results = await vector.search_documents(query=query, limit=top_k, filter_metadata=(filter_md or None))

        # Build a simple answer from top snippets
        snippets: List[str] = []
        citations: List[Dict[str, Any]] = []
        for r in results:
            md = r.get("metadata", {}) or {}
            snippet = r.get("text", "")
            snippets.append(snippet)
            citations.append(
                {
                    "doc_id": md.get("document_id") or md.get("doc_id"),
                    "doc_type": md.get("document_type") or md.get("doc_type"),
                    "page_no": md.get("page_no"),
                    "relevance_score": float(r.get("similarity", 0.0)),
                    "snippet": snippet,
                }
            )

        answer = snippets[0] if snippets else "No relevant context found."
        return {"answer": answer, "citations": citations}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing RAG query: {e}")


@router.get("/capital-account-series/{fund_id}")
async def get_capital_account_series(
    fund_id: str,
    investor_id: Optional[str] = None,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    frequency: Literal["monthly", "quarterly", "annual"] = "quarterly",
    include_forecast: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get capital account time series with analytics and optional forecasting."""
    try:
        # Convert fund_id to UUID
        try:
            fund_uuid = uuid.UUID(fund_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fund_id format")
        
        # Query capital account data
        query = text("""
            SELECT 
                as_of_date,
                period_label,
                beginning_balance,
                ending_balance,
                contributions_period,
                distributions_period,
                distributions_roc_period,
                distributions_gain_period,
                distributions_income_period,
                management_fees_period,
                partnership_expenses_period,
                realized_gain_loss_period,
                unrealized_gain_loss_period,
                total_commitment,
                drawn_commitment,
                unfunded_commitment,
                ownership_pct
            FROM pe_capital_account
            WHERE fund_id = :fund_id
            AND (:investor_id IS NULL OR investor_id = :investor_id)
            AND (:start_date IS NULL OR as_of_date >= :start_date)
            AND (:end_date IS NULL OR as_of_date <= :end_date)
            ORDER BY as_of_date
        """)
        
        result = db.execute(query, {
            'fund_id': str(fund_uuid),
            'investor_id': investor_id,
            'start_date': start_date,
            'end_date': end_date
        })
        
        rows = result.fetchall()
        
        # Process rows into time series
        series = []
        for i, row in enumerate(rows):
            data_point = {
                'as_of_date': row.as_of_date,
                'period_label': row.period_label or f"Q{(row.as_of_date.month-1)//3+1} {row.as_of_date.year}",
                'beginning_balance': float(row.beginning_balance or 0),
                'ending_balance': float(row.ending_balance or 0),
                'contributions_period': float(row.contributions_period or 0),
                'distributions_period': float(row.distributions_period or 0),
                'net_activity': float((row.contributions_period or 0) - (row.distributions_period or 0)),
                'nav_change': float((row.ending_balance or 0) - (row.beginning_balance or 0)),
                'nav_change_pct': 0.0,
                'unfunded_commitment': float(row.unfunded_commitment or 0),
                'drawn_commitment': float(row.drawn_commitment or 0),
                'contribution_pace': 0.0
            }
            
            # Calculate NAV change percentage
            if row.beginning_balance and row.beginning_balance > 0:
                data_point['nav_change_pct'] = (
                    (data_point['nav_change'] / float(row.beginning_balance)) * 100
                )
            
            # Calculate contribution pace
            if row.total_commitment and row.total_commitment > 0:
                data_point['contribution_pace'] = (
                    (float(row.drawn_commitment or 0) / float(row.total_commitment)) * 100
                )
            
            series.append(data_point)
        
        # Add forecast if requested
        if include_forecast and series:
            # Simple forecast logic - to be enhanced
            last_point = series[-1]
            forecast_points = []
            
            for year in range(1, 4):  # 3 year forecast
                forecast_date = date(last_point['as_of_date'].year + year, 12, 31)
                forecast_nav = last_point['ending_balance'] * (1.12 ** year)  # 12% annual growth
                
                forecast_points.append({
                    'as_of_date': forecast_date,
                    'period_label': f"FY {forecast_date.year} (Forecast)",
                    'beginning_balance': series[-1]['ending_balance'] if not forecast_points else forecast_points[-1]['ending_balance'],
                    'ending_balance': forecast_nav,
                    'is_forecast': True
                })
            
            series.extend(forecast_points)
        
        return {
            'fund_id': fund_id,
            'investor_id': investor_id,
            'start_date': start_date,
            'end_date': end_date,
            'frequency': frequency,
            'data_points': len(series),
            'series': series
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching capital account series: {e}")


@router.post("/reconcile/{fund_id}")
async def trigger_reconciliation(
    fund_id: str,
    request: ReconciliationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger reconciliation for a fund."""
    try:
        # Validate fund exists
        try:
            fund_uuid = uuid.UUID(fund_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fund_id format")
        
        # Schedule reconciliation task
        task_id = str(uuid.uuid4())
        
        # In production, this would trigger an async reconciliation job
        # For now, return scheduled status
        return {
            'task_id': task_id,
            'fund_id': fund_id,
            'as_of_date': request.as_of_date,
            'reconciliation_types': request.reconciliation_types,
            'status': 'scheduled',
            'message': 'Reconciliation task scheduled'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering reconciliation: {e}")


@router.get("/extraction-audit/{doc_id}")
async def get_extraction_audit(
    doc_id: str,
    field_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get extraction audit trail for a document."""
    try:
        query = text("""
            SELECT 
                audit_id,
                field_name,
                extracted_value,
                extraction_method,
                confidence_score,
                validation_status,
                validation_errors,
                manual_override,
                override_reason,
                reviewer_id,
                extraction_timestamp,
                review_timestamp
            FROM extraction_audit
            WHERE doc_id = :doc_id
            AND (:field_name IS NULL OR field_name = :field_name)
            ORDER BY extraction_timestamp DESC
        """)
        
        result = db.execute(query, {
            'doc_id': doc_id,
            'field_name': field_name
        })
        
        audits = []
        for row in result:
            audits.append({
                'audit_id': row.audit_id,
                'field_name': row.field_name,
                'extracted_value': row.extracted_value,
                'extraction_method': row.extraction_method,
                'confidence_score': float(row.confidence_score) if row.confidence_score else 0.0,
                'validation_status': row.validation_status,
                'validation_errors': row.validation_errors,
                'manual_override': row.manual_override,
                'override_reason': row.override_reason,
                'reviewer_id': row.reviewer_id,
                'extraction_timestamp': row.extraction_timestamp.isoformat() if row.extraction_timestamp else None,
                'review_timestamp': row.review_timestamp.isoformat() if row.review_timestamp else None
            })
        
        return {
            'doc_id': doc_id,
            'audit_count': len(audits),
            'audits': audits
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching extraction audit: {e}")


@router.post("/manual-override/{doc_id}")
async def apply_manual_override(
    doc_id: str,
    field_overrides: Dict[str, Any],
    reviewer_id: str,
    override_reason: str,
    db: Session = Depends(get_db)
):
    """Apply manual overrides to extracted data."""
    try:
        pe_extractor = MultiMethodExtractor()
        
        # Apply corrections
        result = await pe_extractor.reprocess_with_corrections(
            doc_id=doc_id,
            corrections=field_overrides
        )
        
        if result['status'] == 'success':
            # Update extraction audit
            for field_name, new_value in field_overrides.items():
                query = text("""
                    UPDATE extraction_audit
                    SET manual_override = :new_value,
                        override_reason = :override_reason,
                        reviewer_id = :reviewer_id,
                        review_timestamp = :timestamp
                    WHERE doc_id = :doc_id AND field_name = :field_name
                """)
                
                db.execute(query, {
                    'doc_id': doc_id,
                    'field_name': field_name,
                    'new_value': str(new_value),
                    'override_reason': override_reason,
                    'reviewer_id': reviewer_id,
                    'timestamp': datetime.utcnow()
                })
            
            db.commit()
            
            return {
                'status': 'success',
                'doc_id': doc_id,
                'overrides_applied': len(field_overrides),
                'validation': result.get('validation', {})
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Override failed'))
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error applying manual override: {e}")


async def handle_file(file_path: str, org_code: str, investor_code: str, db: Session = None):
    """Main file processing handler - entry point for watcher.

    Currently a thin wrapper; full extraction/ingestion pipeline is handled
    elsewhere in processors and services.
    """
    print(f"Processing file: {file_path} (org: {org_code}, investor: {investor_code})")
    return {"success": True, "message": "File processing ready"}