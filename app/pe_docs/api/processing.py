"""PE Processing API endpoints - Document processing and job management."""

from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.pe_docs.extractors.multi_method import MultiMethodExtractor
from app.pe_docs.storage.orm import PEStorageORM

router = APIRouter(tags=["PE Processing"])


class ProcessingRequest(BaseModel):
    """Document processing request."""
    file_path: str
    investor_code: str
    force_reprocess: bool = False


class ProcessingResponse(BaseModel):
    """Document processing response."""
    status: str
    doc_id: Optional[str] = None
    message: str
    extraction_summary: Optional[Dict] = None


class JobStatus(BaseModel):
    """Processing job status."""
    job_id: str
    status: str
    file_path: str
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/process-capital-account", response_model=ProcessingResponse)
async def process_capital_account(
    request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Process a capital account statement document.
    
    Extracts capital account data using multi-method extraction.
    """
    try:
        # Initialize extractor and storage
        extractor = MultiMethodExtractor()
        storage = PEStorageORM(db)
        
        # Process the document
        result = await extractor.process_document(
            file_path=request.file_path,
            investor_code=request.investor_code,
            force_reprocess=request.force_reprocess
        )
        
        if result:
            extraction_summary = {
                "extraction_method": result.extraction_method.value if hasattr(result.extraction_method, 'value') else str(result.extraction_method),
                "confidence_score": result.confidence_score,
                "fields_extracted": len(result.extracted_data),
                "processing_time": result.processing_time
            }
            
            return ProcessingResponse(
                status="success",
                doc_id=str(result.doc_id) if hasattr(result, 'doc_id') else None,
                message="Capital account processed successfully",
                extraction_summary=extraction_summary
            )
        else:
            return ProcessingResponse(
                status="failed",
                message="Failed to process capital account document"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capital account processing failed: {str(e)}")


@router.post("/process-quarterly-report", response_model=ProcessingResponse)
async def process_quarterly_report(
    request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Process a quarterly report document.
    
    Extracts quarterly report data and performance metrics.
    """
    try:
        # Initialize extractor
        extractor = MultiMethodExtractor()
        
        # Process the document
        result = await extractor.process_document(
            file_path=request.file_path,
            investor_code=request.investor_code,
            force_reprocess=request.force_reprocess
        )
        
        if result:
            extraction_summary = {
                "extraction_method": result.extraction_method.value if hasattr(result.extraction_method, 'value') else str(result.extraction_method),
                "confidence_score": result.confidence_score,
                "fields_extracted": len(result.extracted_data),
                "processing_time": result.processing_time,
                "document_type": "quarterly_report"
            }
            
            return ProcessingResponse(
                status="success",
                doc_id=str(result.doc_id) if hasattr(result, 'doc_id') else None,
                message="Quarterly report processed successfully",
                extraction_summary=extraction_summary
            )
        else:
            return ProcessingResponse(
                status="failed",
                message="Failed to process quarterly report"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quarterly report processing failed: {str(e)}")


@router.get("/jobs", response_model=List[JobStatus])
async def get_processing_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get processing job status and history."""
    try:
        # This would integrate with a job queue system
        # For now, return a mock response
        jobs = [
            JobStatus(
                job_id="job_001",
                status="completed",
                file_path="/test/sample_document.pdf",
                created_at="2024-01-15T10:30:00Z",
                completed_at="2024-01-15T10:32:00Z"
            ),
            JobStatus(
                job_id="job_002", 
                status="processing",
                file_path="/test/another_document.pdf",
                created_at="2024-01-15T10:35:00Z"
            )
        ]
        
        # Filter by status if provided
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        return jobs[:limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching processing jobs: {str(e)}")


@router.post("/retry-job/{job_id}")
async def retry_failed_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retry a failed processing job."""
    try:
        # This would integrate with job queue system
        # For now, return success response
        
        # Add background task to retry processing
        background_tasks.add_task(_retry_processing_job, job_id)
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Job queued for retry"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrying job: {str(e)}")


async def _retry_processing_job(job_id: str):
    """Background task to retry a processing job."""
    try:
        # Implementation would retrieve job details and reprocess
        # For now, just log the retry attempt
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Retrying processing job: {job_id}")
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to retry job {job_id}: {e}")


# Utility function for file handling (extracted from original API)
async def handle_file(file_path: str, investor_code: str, db: Session) -> Optional[Dict]:
    """Handle file processing - extracted from original API."""
    try:
        extractor = MultiMethodExtractor()
        
        # Process the file
        result = await extractor.process_document(
            file_path=file_path,
            investor_code=investor_code
        )
        
        if result:
            return {
                "doc_id": str(result.doc_id) if hasattr(result, 'doc_id') else None,
                "status": "success",
                "extraction_method": result.extraction_method.value if hasattr(result.extraction_method, 'value') else str(result.extraction_method),
                "confidence": result.confidence_score,
                "fields_count": len(result.extracted_data)
            }
        else:
            return {
                "status": "failed",
                "error": "Processing returned no result"
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e)
        }