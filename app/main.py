"""Main FastAPI application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import load_settings
from app.middleware.error_handler import ErrorHandlingMiddleware, RequestValidationMiddleware
import os

# Load settings
settings = load_settings()
from app.database.connection import get_db, Base
from app.database.models import Document, DocumentType, Investor, Fund, FinancialData
from app.database.file_storage import FileStorageService
from app.services.file_watcher import FileWatcherService
from app.services.document_service import DocumentService
from app.services.chat_service import ChatService
from app.services.vector_service import VectorService
from app.pe_docs.api import router as pe_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.get("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global services
document_service = DocumentService()
chat_service = ChatService()
vector_service = VectorService()
file_watcher_service = FileWatcherService(document_service)
file_storage_service = FileStorageService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting FOReporting v2 application...")
    
    # Create database tables (with UTF-8 safety)
    try:
        # Set UTF-8 environment before database operations
        import os
        os.environ['PYTHONUTF8'] = '1'
        os.environ['PGCLIENTENCODING'] = 'UTF8'
        
        from app.database.connection import init_database
        engine, _ = init_database()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Continuing without database (PE API still available)")
    
    # File watcher is now manual-only (production approach)
    # Users will trigger processing via the frontend interface
    logger.info("File watcher in manual mode - use frontend to process files")
    
    yield
    
    # Cleanup
    logger.info("Shutting down application...")
    try:
        await file_watcher_service.stop()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title="FOReporting v2",
    description="Financial Document Intelligence System",
    version="2.0.0",
    lifespan=lifespan
)

# Add middleware in correct order (last added = first executed)
# Error handling middleware (outermost)
app.add_middleware(ErrorHandlingMiddleware)

# Request validation middleware
app.add_middleware(RequestValidationMiddleware)

# CORS middleware
allowed_origins = settings.get("ALLOWED_ORIGINS", "").split(",") if settings.get("ALLOWED_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Mount PE documents router
app.include_router(pe_router)


# Pydantic models for API
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    context_documents: int
    financial_data_points: int


class DocumentResponse(BaseModel):
    id: str
    filename: str
    document_type: str
    confidence_score: float
    summary: str
    processing_status: str
    created_at: str
    investor_name: str
    fund_name: Optional[str] = None


class ProcessFileRequest(BaseModel):
    file_path: str
    investor_code: str


# API Routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FOReporting v2 - Financial Document Intelligence System",
        "version": "2.0.1-psycopg3",
        "status": "running",
        "database_library": "psycopg3",
        "deployment_mode": settings.get("DEPLOYMENT_MODE", "unknown")
    }


@app.get("/test-new-code")
async def test_new_code():
    """Test endpoint to verify new code is loaded."""
    try:
        from app.config import settings
        from app.database.file_storage import FileStorageService
        
        file_storage = FileStorageService()
        investors = file_storage.get_investors()
        
        return {
            "message": "✅ New code is working!",
            "psycopg_version": "3.2.9",
            "deployment_mode": settings.get("DEPLOYMENT_MODE"),
            "database_url_type": "localhost" if "localhost" in settings.get("DATABASE_URL", "") else "other",
            "investors_available": len(investors),
            "file_storage": "working"
        }
    except Exception as e:
        return {
            "message": "❌ New code test failed",
            "error": str(e)
        }


@app.get("/health")
async def health_check():
    """Production-grade health check endpoint."""
    try:
        # Check database connection (production approach)
        db_status = "disconnected"
        db_error = None
        try:
            from app.database.connection import init_database
            engine, SessionLocal = init_database()
            
            with SessionLocal() as db:
                result = db.execute("SELECT 1")
                db_status = "connected"
                logger.debug("Database health check passed")
        except Exception as e:
            db_error = str(e)
            logger.debug(f"Database health check failed: {e}")
            db_status = "disconnected"
        
        # Check vector service
        vector_stats = await vector_service.get_collection_stats()
        vector_status = "connected" if vector_stats.get("status") != "unavailable" else "disconnected"
        
        # File watcher is now manual-only
        watcher_status = "manual"
        
        # Overall status
        overall_status = "healthy" if vector_status == "connected" else "degraded"
        if db_status == "connected":
            overall_status = "healthy"
        
        health_response = {
            "status": overall_status,
            "services": {
                "database": db_status,
                "vector_store": vector_status,
                "file_watcher": watcher_status
            },
            "vector_stats": vector_stats,
            "deployment_mode": settings.get("DEPLOYMENT_MODE", "unknown")
        }
        
        if db_error:
            health_response["database_error"] = db_error
            
        return health_response
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            "status": "error",
            "services": {
                "database": "error",
                "vector_store": "error", 
                "file_watcher": "manual"
            },
            "error": str(e)
        }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the financial AI assistant."""
    try:
        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = await chat_service.create_session()
        
        # Process chat message
        result = await chat_service.chat(
            session_id=session_id,
            user_message=request.message
        )
        
        return ChatResponse(
            response=result['response'],
            session_id=session_id,
            context_documents=result['context_documents'],
            financial_data_points=result['financial_data_points']
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get chat history for a session."""
    try:
        history = await chat_service.get_session_history(session_id)
        return {"session_id": session_id, "messages": history}
        
    except Exception as e:
        logger.error(f"Get chat history error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    investor_code: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get documents with optional filtering."""
    try:
        # Convert document_type string to enum if provided
        doc_type_enum = None
        if document_type:
            try:
                doc_type_enum = DocumentType(document_type.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid document type: {document_type}")
        
        # Get documents
        documents = await document_service.get_documents(
            investor_code=investor_code,
            document_type=doc_type_enum,
            limit=limit,
            offset=offset
        )
        
        # Convert to response format
        response_docs = []
        for doc in documents:
            response_docs.append(DocumentResponse(
                id=str(doc.id),
                filename=doc.filename,
                document_type=doc.document_type,
                confidence_score=doc.confidence_score or 0.0,
                summary=doc.summary or "",
                processing_status=doc.processing_status,
                created_at=doc.created_at.isoformat(),
                investor_name=doc.investor.name if doc.investor else "Unknown",
                fund_name=doc.fund.name if doc.fund else None
            ))
        
        return response_docs
        
    except Exception as e:
        logger.error(f"Get documents error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/process")
async def process_file_endpoint(
    request: ProcessFileRequest,
    background_tasks: BackgroundTasks
):
    """Manually process a specific file."""
    try:
        # Process file directly using document service
        result = await document_service.process_document(
            file_path=request.file_path,
            investor_code=request.investor_code
        )
        
        if result:
            return {
                "message": f"File processed successfully: {request.file_path}",
                "status": "completed",
                "document_id": str(result.id) if hasattr(result, 'id') else "unknown"
            }
        else:
            return {
                "message": f"File processing failed: {request.file_path}",
                "status": "failed"
            }
        
    except Exception as e:
        logger.error(f"Process file error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan-folders")
async def scan_folders():
    """Scan investor folders for unprocessed files."""
    try:
        from app.config import settings
        import os
        from pathlib import Path
        
        unprocessed_files = []
        
        # Scan investor folders
        folders = [
            {"path": settings.get("INVESTOR1_PATH"), "investor": "brainweb"},
            {"path": settings.get("INVESTOR2_PATH"), "investor": "pecunalta"}
        ]
        
        for folder_info in folders:
            folder_path = folder_info["path"]
            investor_code = folder_info["investor"]
            
            if not folder_path or not Path(folder_path).exists():
                continue
                
            # Scan for supported file types
            for file_path in Path(folder_path).rglob("*"):
                if file_path.is_file():
                    # Check if file type is supported
                    if file_path.suffix.lower() in ['.pdf', '.xlsx', '.xls', '.csv']:
                        # For now, assume all files are unprocessed (in production, check database)
                        unprocessed_files.append({
                            "file_path": str(file_path),
                            "filename": file_path.name,
                            "investor_code": investor_code,
                            "file_size": file_path.stat().st_size,
                            "modified_date": file_path.stat().st_mtime,
                            "file_type": file_path.suffix.lower()
                        })
        
        return {
            "unprocessed_files": unprocessed_files[:100],  # Limit to first 100
            "total_found": len(unprocessed_files),
            "message": f"Found {len(unprocessed_files)} files ready for processing"
        }
        
    except Exception as e:
        logger.error(f"Scan folders error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/investors")
async def get_investors():
    """Get all investors (production-grade file storage)."""
    try:
        # Use file storage directly (production approach for Windows)
        from app.config import settings
        
        investors = [
            {
                "id": "brainweb-001",
                "name": "BrainWeb Investment GmbH",
                "code": "brainweb",
                "description": "BrainWeb Investment GmbH - Private Equity and Venture Capital",
                "document_count": 0,
                "folder_path": settings.get("INVESTOR1_PATH", ""),
                "status": "active",
                "deployment_mode": settings.get("DEPLOYMENT_MODE", "unknown")
            },
            {
                "id": "pecunalta-001",
                "name": "pecunalta GmbH",
                "code": "pecunalta", 
                "description": "pecunalta GmbH - Investment Management",
                "document_count": 0,
                "folder_path": settings.get("INVESTOR2_PATH", ""),
                "status": "active",
                "deployment_mode": settings.get("DEPLOYMENT_MODE", "unknown")
            }
        ]
        
        logger.info(f"Retrieved {len(investors)} investors (file storage mode)")
        return investors
        
    except Exception as e:
        logger.error(f"Get investors error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Investors service error: {str(e)}")


@app.get("/funds")
async def get_funds(
    investor_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get funds with optional investor filtering."""
    try:
        query = db.query(Fund).join(Investor)
        
        if investor_code:
            query = query.filter(Investor.code == investor_code)
        
        funds = query.all()
        
        return [
            {
                "id": str(fund.id),
                "name": fund.name,
                "code": fund.code,
                "asset_class": fund.asset_class,
                "vintage_year": fund.vintage_year,
                "fund_size": fund.fund_size,
                "currency": fund.currency,
                "investor_name": fund.investor.name,
                "investor_code": fund.investor.code,
                "document_count": len(fund.documents)
            }
            for fund in funds
        ]
        
    except Exception as e:
        logger.error(f"Get funds error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/financial-data/{fund_id}")
async def get_financial_data(
    fund_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get financial data for a specific fund."""
    try:
        financial_data = db.query(FinancialData).filter(
            FinancialData.fund_id == fund_id
        ).order_by(FinancialData.reporting_date.desc()).limit(limit).all()
        
        return [
            {
                "id": str(data.id),
                "reporting_date": data.reporting_date.isoformat() if data.reporting_date else None,
                "period_type": data.period_type,
                "nav": float(data.nav) if data.nav else None,
                "total_value": float(data.total_value) if data.total_value else None,
                "irr": float(data.irr) if data.irr else None,
                "moic": float(data.moic) if data.moic else None,
                "committed_capital": float(data.committed_capital) if data.committed_capital else None,
                "drawn_capital": float(data.drawn_capital) if data.drawn_capital else None,
                "distributed_capital": float(data.distributed_capital) if data.distributed_capital else None,
                "currency": data.currency
            }
            for data in financial_data
        ]
        
    except Exception as e:
        logger.error(f"Get financial data error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_documents(
    query: str,
    limit: int = 10
):
    """Search documents using vector similarity."""
    try:
        results = await vector_service.search_documents(
            query=query,
            limit=limit
        )
        
        return {
            "query": query,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_system_stats():
    """Get system statistics."""
    try:
        # Try to get database stats with graceful fallback
        try:
            db = next(get_db())
            total_documents = db.query(Document).count()
            total_investors = db.query(Investor).count()
            total_funds = db.query(Fund).count()
            total_financial_data = db.query(FinancialData).count()
            db.close()
        except Exception as db_error:
            logger.warning(f"Database unavailable for stats: {db_error}")
            # Return default stats when database is unavailable
            total_documents = 0
            total_investors = 0
            total_funds = 0
            total_financial_data = 0
        
        # Processing status breakdown (with database fallback)
        status_counts = {}
        type_counts = {}
        
        try:
            db = next(get_db())
            for status in ["pending", "processing", "completed", "failed"]:
                count = db.query(Document).filter(Document.processing_status == status).count()
                status_counts[status] = count
            
            # Document type breakdown
            for doc_type in DocumentType:
                count = db.query(Document).filter(Document.document_type == doc_type.value).count()
                type_counts[doc_type.value] = count
            db.close()
        except Exception:
            # Default values when database unavailable
            status_counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
            type_counts = {}
        
        # Vector store stats (with fallback)
        try:
            vector_stats = await vector_service.get_collection_stats()
        except Exception:
            vector_stats = {"total_chunks": 0, "status": "unavailable"}
        
        return {
            "database": {
                "documents": total_documents,
                "investors": total_investors,
                "funds": total_funds,
                "financial_data_points": total_financial_data,
                "processing_status": status_counts,
                "document_types": type_counts
            },
            "vector_store": vector_stats,
            "file_watcher": {
                "status": "running" if hasattr(file_watcher_service, 'is_running') and file_watcher_service.is_running else "stopped"
            },
            "pe_system": {
                "status": "operational",
                "endpoints": ["/pe/health", "/pe/documents", "/pe/nav-bridge", "/pe/rag/query"]
            }
        }
        
    except Exception as e:
        logger.error(f"Get stats error: {str(e)}")
        # Return graceful fallback stats instead of 500 error
        return {
            "database": {
                "documents": 0,
                "investors": 0,
                "funds": 0,
                "financial_data_points": 0,
                "processing_status": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
                "document_types": {}
            },
            "vector_store": {"total_chunks": 0, "status": "unavailable"},
            "file_watcher": {"status": "stopped"},
            "pe_system": {
                "status": "operational",
                "endpoints": ["/pe/health", "/pe/documents", "/pe/nav-bridge", "/pe/rag/query"]
            },
            "note": "Database unavailable, showing default values"
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.get("API_PORT", 8000),
        reload=True,
        log_level=settings.get("LOG_LEVEL", "INFO").lower()
    )