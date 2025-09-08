"""FastAPI endpoints for PE documents - Modular version."""

from fastapi import APIRouter

# Import all the modular routers
from app.pe_docs.api.documents import router as documents_router
from app.pe_docs.api.analytics import router as analytics_router  
from app.pe_docs.api.processing import router as processing_router
from app.pe_docs.api.reconciliation import router as reconciliation_router

# Create main PE router
router = APIRouter(prefix="/pe", tags=["PE Documents"])

# Include all sub-routers
router.include_router(documents_router, prefix="", tags=["PE Documents"])
router.include_router(analytics_router, prefix="", tags=["PE Analytics"]) 
router.include_router(processing_router, prefix="", tags=["PE Processing"])
router.include_router(reconciliation_router, prefix="", tags=["PE Reconciliation"])

# Add any remaining endpoints that don't fit in the modules
from typing import Dict, List, Optional
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.vector_service import VectorService


@router.post("/rag/query")
async def query_documents(
    query: str,
    fund_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    """Query PE documents using RAG (Retrieval-Augmented Generation).
    
    Combines semantic search with structured data to answer questions about PE documents.
    """
    try:
        vector_service = VectorService()
        
        # Perform semantic search
        search_results = await vector_service.search_documents(
            query=query,
            limit=limit,
            metadata_filter={
                "fund_id": fund_id,
                "doc_type": doc_type
            } if fund_id or doc_type else None
        )
        
        # Format results for PE context
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                "doc_id": result.get("doc_id"),
                "chunk_id": result.get("chunk_id"), 
                "content": result.get("content"),
                "similarity_score": result.get("similarity_score"),
                "metadata": result.get("metadata", {}),
                "fund_info": result.get("metadata", {}).get("fund_info"),
                "extraction_confidence": result.get("metadata", {}).get("extraction_confidence")
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "search_metadata": {
                "fund_filter": fund_id,
                "doc_type_filter": doc_type,
                "limit": limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


# Legacy endpoint aliases for backward compatibility
@router.get("/capital-account-series/{fund_id}")
async def get_capital_account_series_legacy(fund_id: str, db: Session = Depends(get_db)):
    """Legacy endpoint - redirects to analytics module."""
    from app.pe_docs.api.analytics import get_capital_account_series
    return await get_capital_account_series(fund_id, db)


@router.get("/nav-bridge")  
async def get_nav_bridge_legacy(
    fund_id: Optional[str] = Query(None),
    investor_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Legacy endpoint - redirects to analytics module."""
    from app.pe_docs.api.analytics import get_nav_bridge
    return await get_nav_bridge(fund_id, investor_code, db)