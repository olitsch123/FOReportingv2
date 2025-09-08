"""Main FastAPI application."""

import asyncio
import csv
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import load_settings
from app.middleware.error_handler import (
    ErrorHandlingMiddleware,
    RequestValidationMiddleware,
)

# Load settings
settings = load_settings()
from app.database.connection import Base, get_db
from app.database.file_storage import FileStorageService
from app.database.models import Document, DocumentType, FinancialData, Fund, Investor
from app.pe_docs.api import router as pe_router
from app.security import RequireAPIKey
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.file_watcher import FileWatcherService
from app.services.vector_service import VectorService

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
    
    # File watcher can be controlled via API
    # Start in stopped mode, users can enable via frontend
    logger.info("File watcher initialized (stopped) - control via API/frontend")
    
    yield
    
    # Cleanup
    logger.info("Shutting down application...")
    try:
        await file_watcher_service.stop()
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title="FOReporting v2 - Financial Document Intelligence",
    description="""
    **Enterprise-grade financial document processing system for Private Equity funds.**
    
    ## Features
    - 🤖 **AI-Powered Extraction**: OpenAI-based document classification and data extraction
    - 📊 **PE Analytics**: Capital accounts, NAV analysis, performance metrics
    - 🔍 **Semantic Search**: Vector-based document search and RAG queries  
    - 📈 **Time Series Analysis**: Historical performance tracking and forecasting
    - 🔄 **Data Reconciliation**: Automated validation and discrepancy detection
    - 🛡️ **Enterprise Security**: Input validation, rate limiting, audit trail
    
    ## Architecture
    - **Backend**: FastAPI with async processing
    - **Database**: PostgreSQL with SQLAlchemy ORM
    - **AI/ML**: OpenAI GPT-4, ChromaDB vector store
    - **Frontend**: Streamlit dashboard with Plotly charts
    - **Monitoring**: Prometheus metrics, Grafana dashboards
    
    ## API Documentation
    - 📋 **Main API**: Core document processing and management
    - 🏦 **PE API**: Private equity specific functionality (`/pe/*`)
    - 💬 **Chat API**: Natural language querying (`/chat`)
    - 📊 **Analytics**: Performance metrics and reporting
    
    For detailed implementation guide, see: [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)
    """,
    version="2.0.1-production",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "System",
            "description": "System health, status, and configuration endpoints"
        },
        {
            "name": "Documents", 
            "description": "Document processing, management, and retrieval"
        },
        {
            "name": "PE Documents",
            "description": "Private equity specific document processing and analytics"
        },
        {
            "name": "Analytics",
            "description": "Performance analytics, NAV analysis, and reporting"
        },
        {
            "name": "Chat",
            "description": "AI-powered natural language querying of financial data"
        },
        {
            "name": "File Watcher",
            "description": "File monitoring and automated processing controls"
        }
    ]
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

# Setup instrumentation
try:
    from app.instrumentation.metrics import setup_metrics
    setup_metrics(app)
except ImportError:
    logger.warning("Prometheus instrumentation not available")

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
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint - System information and status.
    
    Returns basic system information including version, status, and configuration.
    Use this endpoint to verify the API is running and accessible.
    
    **Example Response:**
    ```json
    {
        "message": "FOReporting v2 - Financial Document Intelligence System",
        "version": "2.0.1-production",
        "status": "running",
        "features": ["ai_extraction", "pe_analytics", "monitoring"],
        "deployment_mode": "production"
    }
    ```
    """
    return {
        "message": "FOReporting v2 - Financial Document Intelligence System",
        "version": "2.0.1-production",
        "status": "running",
        "features": [
            "ai_extraction",
            "pe_analytics", 
            "semantic_search",
            "time_series_analysis",
            "reconciliation",
            "monitoring",
            "security_hardened"
        ],
        "database_library": "psycopg3",
        "deployment_mode": settings.get("DEPLOYMENT_MODE", "unknown"),
        "documentation": {
            "api_docs": "/docs",
            "redoc": "/redoc", 
            "implementation_guide": "/docs/IMPLEMENTATION_GUIDE.md",
            "security_audit": "/docs/SECURITY_AUDIT.md"
        }
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
                from sqlalchemy import text
                result = db.execute(text("SELECT 1"))
                db_status = "connected"
                logger.debug("Database health check passed")
        except Exception as e:
            db_error = str(e)
            logger.debug(f"Database health check failed: {e}")
            db_status = "disconnected"
        
        # Check vector service
        vector_stats = await vector_service.get_collection_stats()
        vector_status = "connected" if vector_stats.get("status") != "unavailable" else "disconnected"
        
        # File watcher status
        watcher_status = "running" if file_watcher_service.is_running else "stopped"
        
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


@app.post("/chat", response_model=ChatResponse, dependencies=[RequireAPIKey])
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


@app.post("/documents/process", dependencies=[RequireAPIKey])
async def process_file_endpoint(
    request: ProcessFileRequest,
    background_tasks: BackgroundTasks,
    http_request: Request = None
):
    """Manually process a specific file with security validation."""
    try:
        # Import security utilities
        from app.security.validators import validate_processing_request
        from app.security.config import security_config
        from app.security.rate_limiter import check_processing_rate_limit
        
        # Apply rate limiting
        if http_request:
            check_processing_rate_limit(http_request)
        
        # Validate inputs with security checks
        validated_path, validated_investor = validate_processing_request(
            file_path=request.file_path,
            investor_code=request.investor_code,
            allowed_paths=security_config.get_allowed_file_paths()
        )
        
        # Process file with validated inputs
        result = await document_service.process_document(
            file_path=validated_path,
            investor_code=validated_investor
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


@app.get("/folder-tree")
async def get_folder_tree():
    """Get actual Windows directory tree structure."""
    try:
        from pathlib import Path

        from app.config import settings
        
        def build_directory_tree(base_path: str, investor_name: str, max_depth: int = 3) -> dict:
            """Build a proper directory tree structure."""
            path = Path(base_path)
            if not path.exists():
                return {"name": investor_name, "type": "investor", "children": [], "error": "Path not found"}
            
            tree = {
                "name": investor_name,
                "type": "investor", 
                "path": str(path),
                "children": []
            }
            
            try:
                # Scan immediate subdirectories (funds)
                for fund_dir in sorted(path.iterdir()):
                    if not fund_dir.is_dir():
                        continue
                    
                    # Skip excluded folders
                    if fund_dir.name.startswith('!'):
                        continue
                    
                    fund_node = {
                        "name": fund_dir.name,
                        "type": "fund",
                        "path": str(fund_dir),
                        "children": []
                    }
                    
                    # Scan fund subfolders
                    try:
                        for subfolder in sorted(fund_dir.iterdir()):
                            if not subfolder.is_dir():
                                continue
                            
                            # Skip excluded subfolders
                            if subfolder.name.startswith('!'):
                                continue
                            
                            # Count files in subfolder
                            file_count = 0
                            file_types = {}
                            
                            for file_path in subfolder.rglob("*"):
                                if file_path.is_file():
                                    # Apply exclusion rules
                                    if file_path.suffix.lower() == '.py':
                                        continue
                                    if file_path.name.endswith('_Fund_Documents.xlsx') and '[' in file_path.name:
                                        continue
                                    
                                    # Skip files in excluded folders
                                    skip_file = False
                                    for parent in file_path.parents:
                                        if parent.name.startswith('!'):
                                            skip_file = True
                                            break
                                    if skip_file:
                                        continue
                                    
                                    if file_path.suffix.lower() in ['.pdf', '.xlsx', '.xls', '.csv', '.docx']:
                                        file_count += 1
                                        ext = file_path.suffix.lower()
                                        file_types[ext] = file_types.get(ext, 0) + 1
                            
                            # Get processing status for this subfolder
                            processed_count = 0
                            try:
                                # Quick check of document tracker for this path
                                from app.database.connection import get_db_session
                                with get_db_session() as db:
                                    from sqlalchemy import text
                                    result = db.execute(text("""
                                        SELECT COUNT(*) FROM document_tracker 
                                        WHERE file_path LIKE :path AND status = 'completed'
                                    """), {"path": f"{str(subfolder)}%"}).scalar()
                                    processed_count = result or 0
                            except:
                                processed_count = 0
                            
                            # Determine status
                            if processed_count == 0:
                                status = "ready"
                            elif processed_count >= file_count:
                                status = "completed"
                            else:
                                status = "mixed"
                            
                            subfolder_node = {
                                "name": subfolder.name,
                                "type": "subfolder",
                                "path": str(subfolder),
                                "file_count": file_count,
                                "processed_count": processed_count,
                                "file_types": file_types,
                                "processing_status": status,
                                "children": []
                            }
                            
                            fund_node["children"].append(subfolder_node)
                        
                        # Calculate total files for fund
                        fund_file_count = sum(child["file_count"] for child in fund_node["children"])
                        fund_node["file_count"] = fund_file_count
                        
                    except PermissionError:
                        fund_node["error"] = "Permission denied"
                    
                    tree["children"].append(fund_node)
                
            except PermissionError:
                tree["error"] = "Permission denied"
            
            return tree
        
        # Build trees for both investors
        investor_trees = []
        
        investor_paths = [
            {"path": settings.get("INVESTOR1_PATH"), "name": "BrainWeb Investment"},
            {"path": settings.get("INVESTOR2_PATH"), "name": "Pecunalta"}
        ]
        
        for investor_info in investor_paths:
            if investor_info["path"]:
                tree = build_directory_tree(investor_info["path"], investor_info["name"])
                investor_trees.append(tree)
        
        return {
            "investors": investor_trees,
            "total_investors": len(investor_trees)
        }
        
    except Exception as e:
        logger.error(f"Error building folder tree: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scan-folders")
async def scan_folders():
    """Scan investor folders for unprocessed files."""
    try:
        import os
        from pathlib import Path

        from app.config import settings
        
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
                    # Apply exclusion rules
                    # 1. Skip Python scripts
                    if file_path.suffix.lower() == '.py':
                        continue
                    
                    # 2. Skip files matching [Date]_Fund_Documents.xlsx pattern
                    if file_path.name.endswith('_Fund_Documents.xlsx') and '[' in file_path.name:
                        continue
                    
                    # 3. Skip files in folders starting with "!"
                    skip_file = False
                    for parent in file_path.parents:
                        if parent.name.startswith('!'):
                            skip_file = True
                            break
                    if skip_file:
                        continue
                    
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


@app.post("/file-watcher/start")
async def start_file_watcher():
    """Start the file watcher service."""
    try:
        if not file_watcher_service.is_running:
            await file_watcher_service.start()
            return {"status": "started", "message": "File watcher started successfully"}
        else:
            return {"status": "already_running", "message": "File watcher is already running"}
    except Exception as e:
        logger.error(f"Failed to start file watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/file-watcher/stop")
async def stop_file_watcher():
    """Stop the file watcher service."""
    try:
        if file_watcher_service.is_running:
            await file_watcher_service.stop()
            return {"status": "stopped", "message": "File watcher stopped successfully"}
        else:
            return {"status": "already_stopped", "message": "File watcher is not running"}
    except Exception as e:
        logger.error(f"Failed to stop file watcher: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/file-watcher/status")
async def get_file_watcher_status():
    """Get the status of the file watcher service."""
    try:
        watched_folders = []
        discovered_files = []
        scan_errors = []
        
        # Get configured paths 
        investor1_path = settings.get("INVESTOR1_PATH", "")
        investor2_path = settings.get("INVESTOR2_PATH", "")
        
        # Note: The paths are already correct in the environment
        # The issue is JSON encoding in the response
        
        folders_config = [
            {"name": "Investor 1", "path": investor1_path},
            {"name": "Investor 2", "path": investor2_path}
        ]
        
        for folder_info in folders_config:
            if folder_info["path"]:
                try:
                    path = Path(folder_info["path"])
                    exists = path.exists()
                    file_count = 0
                    
                    if exists:
                        # Count supported files (whether running or not)
                        extensions = ['.pdf', '.xlsx', '.xls', '.csv', '.txt', '.docx']
                        for ext in extensions:
                            files = list(path.rglob(f"*{ext}"))
                            file_count += len(files)
                            # Log for debugging
                            if files and not discovered_files:
                                logger.info(f"Found {len(files)} {ext} files in {folder_info['name']}")
                    
                    watched_folders.append({
                        "name": folder_info["name"],
                        "path": str(path),
                        "exists": exists,
                        "file_count": file_count
                    })
                except Exception as e:
                    scan_errors.append(f"{folder_info['name']}: {str(e)}")
        
        # Get recent discoveries from queue
        if file_watcher_service.is_running and hasattr(file_watcher_service.handler, 'file_timestamps'):
            recent_files = sorted(
                file_watcher_service.handler.file_timestamps.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Last 10 files
            
            discovered_files = [
                {
                    "path": Path(file_path).name,
                    "timestamp": timestamp.isoformat(),
                    "status": "queued" if file_path in file_watcher_service.handler.processing_queue else "processed"
                }
                for file_path, timestamp in recent_files
            ]
        
        response_data = {
            "is_running": file_watcher_service.is_running,
            "watched_folders": watched_folders,
            "queue_size": len(file_watcher_service.handler.processing_queue) if file_watcher_service.is_running else 0,
            "discovered_files": discovered_files,
            "scan_errors": scan_errors,
            "total_files_found": sum(f["file_count"] for f in watched_folders)
        }
        
        # Return with proper UTF-8 encoding
        return JSONResponse(
            content=response_data,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Failed to get file watcher status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/file-watcher/scan")
async def trigger_file_scan(background_tasks: BackgroundTasks):
    """Manually trigger a scan of watched folders."""
    try:
        if not file_watcher_service.is_running:
            # Start temporarily for scan
            await file_watcher_service.start()
            scan_started = True
        else:
            scan_started = False
        
        # Get folders  
        investor1_path = settings.get("INVESTOR1_PATH", "")
        investor2_path = settings.get("INVESTOR2_PATH", "")
        
        scan_results = {
            "folders_scanned": [],
            "files_discovered": 0,
            "errors": []
        }
        
        folders = [
            {"name": "Investor 1", "path": investor1_path},
            {"name": "Investor 2", "path": investor2_path}
        ]
        
        for folder_info in folders:
            if folder_info["path"]:
                try:
                    path = Path(folder_info["path"])
                    if path.exists():
                        file_count = 0
                        extensions = ['.pdf', '.xlsx', '.xls', '.csv', '.txt', '.docx']
                        
                        for ext in extensions:
                            # Skip Python files
                            if ext.lower() == '.py':
                                continue
                                
                            files = list(path.rglob(f"*{ext}"))
                            
                            # Apply exclusion rules to each file
                            filtered_files = []
                            for file_path in files:
                                # Skip files matching [Date]_Fund_Documents.xlsx pattern
                                if file_path.name.endswith('_Fund_Documents.xlsx') and '[' in file_path.name:
                                    continue
                                
                                # Skip files in folders starting with "!"
                                skip_file = False
                                for parent in file_path.parents:
                                    if parent.name.startswith('!'):
                                        skip_file = True
                                        break
                                if skip_file:
                                    continue
                                    
                                filtered_files.append(file_path)
                            
                            file_count += len(filtered_files)
                        
                        scan_results["folders_scanned"].append({
                            "name": folder_info["name"],
                            "path": str(path),
                            "files_found": file_count
                        })
                        scan_results["files_discovered"] += file_count
                    else:
                        scan_results["errors"].append(f"{folder_info['name']}: Folder does not exist")
                except Exception as e:
                    scan_results["errors"].append(f"{folder_info['name']}: {str(e)}")
        
        # If we started the watcher just for scan, schedule to stop it
        if scan_started:
            background_tasks.add_task(stop_watcher_after_scan)
        
        return {
            "status": "scan_completed",
            "results": scan_results,
            "message": f"Discovered {scan_results['files_discovered']} files in {len(scan_results['folders_scanned'])} folders"
        }
    except Exception as e:
        logger.error(f"Failed to trigger scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def stop_watcher_after_scan():
    """Stop file watcher after manual scan completes."""
    await asyncio.sleep(5)  # Give time for processing
    if file_watcher_service.is_running:
        await file_watcher_service.stop()


# Document Tracker endpoints
@app.get("/document-tracker/stats")
async def get_document_tracker_stats(db: Session = Depends(get_db)):
    """Get document tracking statistics."""
    try:
        from app.database.document_tracker import DocumentTrackerService
        tracker_service = DocumentTrackerService(db)
        stats = tracker_service.get_processing_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get tracker stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document-tracker/export")
async def export_document_tracker(
    status: Optional[str] = None,
    format: str = "csv",
    db: Session = Depends(get_db)
):
    """Export document tracking data as CSV."""
    try:
        from app.database.document_tracker import DocumentTrackerService
        tracker_service = DocumentTrackerService(db)
        documents = tracker_service.get_documents_for_export(status=status)
        
        if format == "json":
            return JSONResponse(content=documents)
        
        # Create CSV in memory
        output = io.StringIO()
        
        if documents:
            fieldnames = documents[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(documents)
        else:
            # Empty CSV with headers
            fieldnames = ['id', 'file_name', 'file_path', 'file_hash', 'status', 
                         'first_seen', 'last_processed', 'error_message']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
        
        # Return as streaming response
        output.seek(0)
        filename = f"document_tracker_{status or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to export document tracker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/document-tracker/reprocess/{file_hash}", dependencies=[RequireAPIKey])
async def reprocess_document(
    file_hash: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Mark a document for reprocessing."""
    try:
        from app.database.document_tracker import (
            DocumentTracker,
            DocumentTrackerService,
        )

        # Find the document
        doc = db.query(DocumentTracker).filter_by(file_hash=file_hash).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Mark as discovered to trigger reprocessing
        doc.status = 'discovered'
        doc.error_message = None
        db.commit()
        
        # If file watcher is running, it will pick it up
        # Otherwise, trigger manual processing
        if not file_watcher_service.is_running:
            background_tasks.add_task(process_single_file, doc.file_path)
        
        return {
            "status": "queued",
            "file_hash": file_hash,
            "file_name": doc.file_name,
            "message": "Document queued for reprocessing"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reprocess document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_single_file(file_path: str):
    """Process a single file in the background."""
    try:
        # Use the file watcher's process method
        if hasattr(file_watcher_service, 'handler'):
            await file_watcher_service.handler._process_file(file_path)
    except Exception as e:
        logger.error(f"Failed to process file {file_path}: {e}")


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
                "status": "running" if file_watcher_service.is_running else "stopped",
                "watched_folders": len([f for f in [settings.get("INVESTOR1_PATH"), settings.get("INVESTOR2_PATH")] if f]) if file_watcher_service.is_running else 0
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