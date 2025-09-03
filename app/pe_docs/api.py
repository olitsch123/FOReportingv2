"""FastAPI endpoints for PE documents (production-grade minimal set)."""
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.database.connection import get_db
from app.database.models import Document, Investor, Fund, FinancialData
from app.services.vector_service import VectorService


router = APIRouter(prefix="/pe", tags=["PE Documents"])


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

        stmt = select(
            func.date_trunc("month", FinancialData.reporting_date).label("period_end"),
            func.max(FinancialData.nav).label("nav_end"),
        ).where(FinancialData.fund_id == fund_id)

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
        stmt = (
            select(FinancialData)
            .where(and_(FinancialData.fund_id == fund_id, FinancialData.reporting_date <= ad))
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


async def handle_file(file_path: str, org_code: str, investor_code: str, db: Session = None):
    """Main file processing handler - entry point for watcher.

    Currently a thin wrapper; full extraction/ingestion pipeline is handled
    elsewhere in processors and services.
    """
    print(f"Processing file: {file_path} (org: {org_code}, investor: {investor_code})")
    return {"success": True, "message": "File processing ready"}