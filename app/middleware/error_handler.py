"""Global error handling middleware for FOReporting v2."""

import time
import traceback
import uuid
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError, IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
from structlog import get_logger

from app.exceptions import FOReportingError, handle_database_error, handle_api_error

logger = get_logger()


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Production-grade error handling middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle all exceptions globally with proper logging and responses."""
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Track request timing
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log successful requests
            process_time = time.time() - start_time
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time=round(process_time, 3)
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except HTTPException as e:
            # Handle expected HTTP exceptions
            process_time = time.time() - start_time
            logger.warning(
                "http_exception",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=e.status_code,
                detail=e.detail,
                process_time=round(process_time, 3)
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.status_code,
                        "message": e.detail,
                        "request_id": request_id
                    }
                },
                headers={"X-Request-ID": request_id}
            )
            
        except ValidationError as e:
            # Handle Pydantic validation errors
            process_time = time.time() - start_time
            logger.error(
                "validation_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                errors=e.errors(),
                process_time=round(process_time, 3)
            )
            
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": 422,
                        "message": "Validation error",
                        "details": e.errors(),
                        "request_id": request_id
                    }
                },
                headers={"X-Request-ID": request_id}
            )
        
        except FOReportingError as e:
            # Handle our custom exceptions
            process_time = time.time() - start_time
            
            # Determine appropriate HTTP status code
            status_code = self._get_status_code_for_error(e)
            
            logger.error(
                "forreporting_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error_type=e.__class__.__name__,
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                process_time=round(process_time, 3)
            )
            
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": {
                        **e.to_dict(),
                        "request_id": request_id,
                        "timestamp": time.time()
                    }
                },
                headers={"X-Request-ID": request_id}
            )
            
        except IntegrityError as e:
            # Handle database integrity errors
            process_time = time.time() - start_time
            logger.error(
                "database_integrity_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time=round(process_time, 3)
            )
            
            return JSONResponse(
                status_code=409,
                content={
                    "error": {
                        "code": 409,
                        "message": "Database integrity error - possible duplicate or constraint violation",
                        "request_id": request_id
                    }
                },
                headers={"X-Request-ID": request_id}
            )
            
        except DatabaseError as e:
            # Handle general database errors
            process_time = time.time() - start_time
            logger.error(
                "database_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time=round(process_time, 3)
            )
            
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": 503,
                        "message": "Database service temporarily unavailable",
                        "request_id": request_id
                    }
                },
                headers={"X-Request-ID": request_id}
            )
            
        except Exception as e:
            # Handle unexpected errors
            process_time = time.time() - start_time
            
            # Log full traceback for debugging
            logger.error(
                "unexpected_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc(),
                process_time=round(process_time, 3)
            )
            
            # Return generic error to client (don't expose internals)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": 500,
                        "message": "An unexpected error occurred",
                        "request_id": request_id
                    }
                },
                headers={"X-Request-ID": request_id}
            )


    def _get_status_code_for_error(self, error: FOReportingError) -> int:
        """Map custom exceptions to appropriate HTTP status codes."""
        error_type = error.__class__.__name__
        
        # Map specific error types to HTTP status codes
        status_map = {
            "DocumentNotFoundError": 404,
            "InvestorNotFoundError": 404,
            "FundNotFoundError": 404,
            "ProcessorNotAvailableError": 422,
            "ValidationError": 422,
            "ConfigurationError": 500,
            "DatabaseConnectionError": 503,
            "OpenAIError": 503,
            "VectorStoreError": 503,
            "ExtractionError": 422,
            "ReconciliationError": 409,
            "PerformanceCalculationError": 422,
            "FileWatcherError": 500,
            "DependencyError": 500
        }
        
        return status_map.get(error_type, 500)  # Default to 500 for unknown errors


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and sanitization."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate and sanitize incoming requests."""
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 100 * 1024 * 1024:  # 100MB limit
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": 413,
                                "message": "Request entity too large (max 100MB)"
                            }
                        }
                    )
            except ValueError:
                pass
        
        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not any(ct in content_type for ct in ["application/json", "multipart/form-data"]):
                return JSONResponse(
                    status_code=415,
                    content={
                        "error": {
                            "code": 415,
                            "message": "Unsupported media type. Use application/json or multipart/form-data"
                        }
                    }
                )
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response