"""PE Reconciliation API endpoints - Data validation and reconciliation workflows."""

from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.pe_docs.reconciliation.openai_agent import FinancialReconciliationAgent
from app.pe_docs.storage.orm import PEStorageORM

router = APIRouter(tags=["PE Reconciliation"])


class ReconciliationRequest(BaseModel):
    """Reconciliation request."""
    fund_id: str
    reconciliation_type: str = "full"  # full, nav_only, performance_only
    tolerance_override: Optional[Dict[str, float]] = None


class ReconciliationResult(BaseModel):
    """Reconciliation result."""
    reconciliation_id: str
    fund_id: str
    status: str
    summary: Dict
    discrepancies: List[Dict]
    recommendations: List[str]


@router.post("/reconcile", response_model=ReconciliationResult)
async def run_reconciliation(
    request: ReconciliationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Run comprehensive reconciliation for a fund.
    
    Validates data consistency across different document types and calculates
    performance metrics with cross-validation.
    """
    try:
        # Initialize reconciliation agent
        agent = FinancialReconciliationAgent(db)
        storage = PEStorageORM(db)
        
        # Get fund data
        fund_data = storage.get_fund_by_id(request.fund_id)
        if not fund_data:
            raise HTTPException(status_code=404, detail="Fund not found")
        
        # Run reconciliation based on type
        if request.reconciliation_type == "nav_only":
            result = await agent.reconcile_nav_data(request.fund_id)
        elif request.reconciliation_type == "performance_only":
            result = await agent.reconcile_performance_metrics(request.fund_id)
        else:  # full reconciliation
            result = await agent.run_full_reconciliation(request.fund_id)
        
        # Apply tolerance overrides if provided
        if request.tolerance_override:
            result = await agent.apply_tolerance_overrides(result, request.tolerance_override)
        
        # Store reconciliation results
        reconciliation_id = await storage.store_reconciliation_result(
            fund_id=request.fund_id,
            reconciliation_type=request.reconciliation_type,
            result=result
        )
        
        return ReconciliationResult(
            reconciliation_id=reconciliation_id,
            fund_id=request.fund_id,
            status=result.get("status", "completed"),
            summary=result.get("summary", {}),
            discrepancies=result.get("discrepancies", []),
            recommendations=result.get("recommendations", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.get("/reconciliation-history")
async def get_reconciliation_history(
    fund_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get reconciliation history and results."""
    try:
        storage = PEStorageORM(db)
        
        # Get reconciliation history
        history = storage.get_reconciliation_history(
            fund_id=fund_id,
            limit=limit
        )
        
        return {
            "reconciliations": history,
            "summary": {
                "total_reconciliations": len(history),
                "successful": len([r for r in history if r.get("status") == "success"]),
                "with_discrepancies": len([r for r in history if r.get("discrepancies")])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reconciliation history: {str(e)}")


@router.get("/reconciliation/{reconciliation_id}")
async def get_reconciliation_details(
    reconciliation_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed reconciliation results."""
    try:
        storage = PEStorageORM(db)
        
        # Get reconciliation details
        details = storage.get_reconciliation_details(reconciliation_id)
        
        if not details:
            raise HTTPException(status_code=404, detail="Reconciliation not found")
        
        return {
            "reconciliation_id": reconciliation_id,
            "details": details,
            "timestamp": details.get("created_at"),
            "fund_id": details.get("fund_id"),
            "status": details.get("status")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reconciliation details: {str(e)}")


@router.post("/reconcile-nav/{fund_id}")
async def reconcile_nav_only(
    fund_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Quick NAV reconciliation for a specific fund."""
    try:
        agent = FinancialReconciliationAgent(db)
        
        # Run NAV-only reconciliation
        result = await agent.reconcile_nav_data(fund_id)
        
        return {
            "fund_id": fund_id,
            "reconciliation_type": "nav_only",
            "status": result.get("status"),
            "nav_sources": result.get("nav_sources", []),
            "discrepancies": result.get("discrepancies", []),
            "tolerance_check": result.get("tolerance_check", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NAV reconciliation failed: {str(e)}")


@router.post("/validate-extraction/{doc_id}")
async def validate_extraction(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """Validate extracted data for a specific document."""
    try:
        storage = PEStorageORM(db)
        
        # Get document and extraction data
        doc_data = storage.get_document_extraction_data(doc_id)
        
        if not doc_data:
            raise HTTPException(status_code=404, detail="Document or extraction data not found")
        
        # Run validation
        from app.pe_docs.validation import DocumentValidator
        validator = DocumentValidator()
        
        validation_result = validator.validate_extraction(doc_data)
        
        return {
            "doc_id": doc_id,
            "validation_status": validation_result.get("status"),
            "validation_errors": validation_result.get("errors", []),
            "validation_warnings": validation_result.get("warnings", []),
            "field_validations": validation_result.get("field_validations", {}),
            "overall_score": validation_result.get("overall_score", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction validation failed: {str(e)}")


@router.post("/manual-override/{doc_id}")
async def apply_manual_override(
    doc_id: str,
    overrides: Dict,
    reason: str,
    db: Session = Depends(get_db),
):
    """Apply manual data overrides to extracted document data."""
    try:
        storage = PEStorageORM(db)
        
        # Validate the document exists
        doc_data = storage.get_document_extraction_data(doc_id)
        if not doc_data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Apply overrides with audit trail
        override_result = storage.apply_manual_overrides(
            doc_id=doc_id,
            overrides=overrides,
            reason=reason,
            applied_by="api_user"  # In production, get from auth context
        )
        
        return {
            "doc_id": doc_id,
            "status": "success",
            "overrides_applied": len(overrides),
            "audit_trail_id": override_result.get("audit_trail_id"),
            "message": "Manual overrides applied successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual override failed: {str(e)}")


@router.get("/extraction-audit/{doc_id}")
async def get_extraction_audit(
    doc_id: str,
    db: Session = Depends(get_db),
):
    """Get complete extraction audit trail for a document."""
    try:
        storage = PEStorageORM(db)
        
        # Get audit trail
        audit_data = storage.get_extraction_audit_trail(doc_id)
        
        if not audit_data:
            raise HTTPException(status_code=404, detail="No audit data found for document")
        
        return {
            "doc_id": doc_id,
            "audit_trail": audit_data,
            "extraction_history": audit_data.get("extraction_history", []),
            "manual_overrides": audit_data.get("manual_overrides", []),
            "validation_results": audit_data.get("validation_results", []),
            "reconciliation_checks": audit_data.get("reconciliation_checks", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching extraction audit: {str(e)}")