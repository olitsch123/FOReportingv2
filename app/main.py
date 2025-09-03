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
import os

# Load settings
settings = load_settings()
from app.database.connection import get_db, engine, Base
from app.database.models import Document, DocumentType, Investor, Fund, FinancialData
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
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.info("Continuing without database (PE API still available)")
    
    # Start file watcher (with UTF-8 safety) if enabled
    try:
        enable_watcher = os.getenv("ENABLE_FILE_WATCHER", "true").lower() == "true"
        if enable_watcher:
            # Start watcher without blocking startup
            asyncio.create_task(file_watcher_service.start())
            logger.info("File watcher service starting in background")
        else:
            logger.info("File watcher disabled by ENABLE_FILE_WATCHER=false")
    except Exception as e:
        logger.warning(f"File watcher failed to start: {e}")
        logger.info("Continuing without file watcher")
    
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check vector service
        vector_stats = await vector_service.get_collection_stats()
        
        return {
            "status": "healthy",
            "services": {
                "database": "connected",
                "vector_store": "connected",
                "file_watcher": "running" if file_watcher_service.is_running else "stopped"
            },
            "vector_stats": vector_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


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
        # Add processing task to background
        background_tasks.add_task(
            file_watcher_service.process_single_file,
            request.file_path
        )
        
        return {
            "message": f"File queued for processing: {request.file_path}",
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Process file error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/investors")
async def get_investors(db: Session = Depends(get_db)):
    """Get all investors."""
    try:
        investors = db.query(Investor).all()
        return [
            {
                "id": str(investor.id),
                "name": investor.name,
                "code": investor.code,
                "description": investor.description,
                "document_count": len(investor.documents)
            }
            for investor in investors
        ]
        
    except Exception as e:
        logger.error(f"Get investors error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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