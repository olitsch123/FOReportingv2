"""PE Documents API endpoints - Document CRUD and listing."""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Document, Investor

router = APIRouter(tags=["PE Documents - CRUD"])


class DocumentMetadata(BaseModel):
    """Document metadata for PE docs."""
    doc_id: str
    doc_type: str
    investor_code: str
    fund_id: Optional[str] = None
    period_date: Optional[date] = None
    extraction_status: str


@router.get("/documents", response_model=List[DocumentMetadata])
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
        filtered_docs = []
        for row in rows:
            file_path = row.file_path or ""
            # Skip files in excluded folders (starting with "!")
            if "\\!" in file_path or "/!" in file_path:
                continue
            
            filtered_docs.append({
                "doc_id": str(row.id),
                "file_name": row.file_name,
                "doc_type": row.doc_type,
                "investor_code": row.investor_code,
                "fund_id": str(row.fund_id) if row.fund_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "period_date": None,  # Will be populated from extraction data if available
                "extraction_status": "completed"  # Simplified for now
            })
        
        return filtered_docs
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching PE documents: {str(e)}")


@router.get("/documents/{doc_id}")
async def get_document_details(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific PE document."""
    try:
        # Get document with related data
        stmt = (
            select(Document, Investor)
            .join(Investor, Investor.id == Document.investor_id)
            .where(Document.id == doc_id)
        )
        
        result = db.execute(stmt).first()
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document, investor = result
        
        return {
            "doc_id": str(document.id),
            "filename": document.filename,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "document_type": document.document_type,
            "confidence_score": document.confidence_score,
            "processing_status": document.processing_status,
            "summary": document.summary,
            "investor": {
                "code": investor.code,
                "name": investor.name
            },
            "fund_id": str(document.fund_id) if document.fund_id else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching document details: {str(e)}")


@router.get("/health")
async def pe_health_check():
    """PE system health check endpoint."""
    try:
        # Quick health check for PE components
        components = {
            "extractors": "operational",
            "classifiers": "operational", 
            "storage": "operational",
            "reconciliation": "operational"
        }
        
        # Check if we can import key components
        try:
            from app.pe_docs.extractors.multi_method import MultiMethodExtractor
            from app.pe_docs.classifiers import PEDocumentClassifier
            from app.pe_docs.storage.orm import PEStorageORM
            components["import_status"] = "success"
        except ImportError as e:
            components["import_status"] = f"failed: {str(e)}"
            components["extractors"] = "unavailable"
        
        overall_status = "healthy" if all(
            status in ["operational", "success"] 
            for status in components.values()
        ) else "degraded"
        
        return {
            "status": overall_status,
            "components": components,
            "version": "2.0.1",
            "timestamp": date.today().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "components": {"all": "unavailable"}
        }