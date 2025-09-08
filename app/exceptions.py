"""Custom exception classes for FOReporting v2."""

from typing import Any, Dict, Optional


class FOReportingError(Exception):
    """Base exception for all FOReporting errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


# Document Processing Exceptions
class DocumentProcessingError(FOReportingError):
    """Base exception for document processing errors."""
    pass


class DocumentNotFoundError(DocumentProcessingError):
    """Document not found error."""
    
    def __init__(self, file_path: str, details: Optional[Dict] = None):
        super().__init__(
            message=f"Document not found: {file_path}",
            error_code="DOC_NOT_FOUND",
            details={"file_path": file_path, **(details or {})}
        )


class ProcessorNotAvailableError(DocumentProcessingError):
    """No processor available for document type."""
    
    def __init__(self, file_path: str, file_type: str):
        super().__init__(
            message=f"No processor available for file type: {file_type}",
            error_code="PROCESSOR_UNAVAILABLE",
            details={"file_path": file_path, "file_type": file_type}
        )


class ExtractionError(DocumentProcessingError):
    """Data extraction failed."""
    
    def __init__(self, file_path: str, extraction_method: str, reason: str):
        super().__init__(
            message=f"Data extraction failed using {extraction_method}: {reason}",
            error_code="EXTRACTION_FAILED",
            details={
                "file_path": file_path,
                "extraction_method": extraction_method,
                "reason": reason
            }
        )


class ValidationError(DocumentProcessingError):
    """Data validation failed."""
    
    def __init__(self, field_name: str, value: Any, validation_rule: str):
        super().__init__(
            message=f"Validation failed for field '{field_name}': {validation_rule}",
            error_code="VALIDATION_FAILED",
            details={
                "field_name": field_name,
                "value": str(value),
                "validation_rule": validation_rule
            }
        )


# Database Exceptions
class DatabaseError(FOReportingError):
    """Base exception for database errors."""
    pass


class InvestorNotFoundError(DatabaseError):
    """Investor not found error."""
    
    def __init__(self, investor_code: str):
        super().__init__(
            message=f"Investor not found: {investor_code}",
            error_code="INVESTOR_NOT_FOUND",
            details={"investor_code": investor_code}
        )


class FundNotFoundError(DatabaseError):
    """Fund not found error."""
    
    def __init__(self, fund_id: str):
        super().__init__(
            message=f"Fund not found: {fund_id}",
            error_code="FUND_NOT_FOUND", 
            details={"fund_id": fund_id}
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection failed."""
    
    def __init__(self, connection_string: str, reason: str):
        super().__init__(
            message=f"Database connection failed: {reason}",
            error_code="DB_CONNECTION_FAILED",
            details={"connection_string": connection_string, "reason": reason}
        )


# API and External Service Exceptions
class APIError(FOReportingError):
    """Base exception for API errors."""
    pass


class OpenAIError(APIError):
    """OpenAI API errors."""
    
    def __init__(self, operation: str, reason: str, api_response: Optional[Dict] = None):
        super().__init__(
            message=f"OpenAI API error during {operation}: {reason}",
            error_code="OPENAI_API_ERROR",
            details={
                "operation": operation,
                "reason": reason,
                "api_response": api_response
            }
        )


class VectorStoreError(APIError):
    """Vector store operation errors."""
    
    def __init__(self, operation: str, store_type: str, reason: str):
        super().__init__(
            message=f"Vector store error ({store_type}) during {operation}: {reason}",
            error_code="VECTOR_STORE_ERROR",
            details={
                "operation": operation,
                "store_type": store_type,
                "reason": reason
            }
        )


class FileWatcherError(FOReportingError):
    """File watcher service errors."""
    
    def __init__(self, operation: str, folder_path: str, reason: str):
        super().__init__(
            message=f"File watcher error during {operation} on {folder_path}: {reason}",
            error_code="FILE_WATCHER_ERROR",
            details={
                "operation": operation,
                "folder_path": folder_path,
                "reason": reason
            }
        )


# Configuration and Setup Exceptions  
class ConfigurationError(FOReportingError):
    """Configuration errors."""
    
    def __init__(self, config_key: str, reason: str):
        super().__init__(
            message=f"Configuration error for '{config_key}': {reason}",
            error_code="CONFIG_ERROR",
            details={"config_key": config_key, "reason": reason}
        )


class DependencyError(FOReportingError):
    """Missing or incompatible dependency errors."""
    
    def __init__(self, dependency: str, required_version: str, current_version: Optional[str] = None):
        super().__init__(
            message=f"Dependency error: {dependency} (required: {required_version}, current: {current_version or 'not installed'})",
            error_code="DEPENDENCY_ERROR",
            details={
                "dependency": dependency,
                "required_version": required_version,
                "current_version": current_version
            }
        )


# PE-Specific Exceptions
class PEExtractionError(ExtractionError):
    """PE-specific extraction errors."""
    
    def __init__(self, document_type: str, field_name: str, reason: str):
        super().__init__(
            file_path="",  # Will be set by caller
            extraction_method="pe_extraction",
            reason=f"PE extraction failed for {document_type}.{field_name}: {reason}"
        )
        self.details.update({
            "document_type": document_type,
            "field_name": field_name
        })


class ReconciliationError(FOReportingError):
    """Data reconciliation errors."""
    
    def __init__(self, fund_id: str, metric: str, discrepancy: float, tolerance: float):
        super().__init__(
            message=f"Reconciliation failed for {metric}: discrepancy {discrepancy:.2f} exceeds tolerance {tolerance:.2f}",
            error_code="RECONCILIATION_FAILED",
            details={
                "fund_id": fund_id,
                "metric": metric,
                "discrepancy": discrepancy,
                "tolerance": tolerance
            }
        )


class PerformanceCalculationError(FOReportingError):
    """Performance metric calculation errors."""
    
    def __init__(self, metric: str, reason: str, input_data: Optional[Dict] = None):
        super().__init__(
            message=f"Performance calculation failed for {metric}: {reason}",
            error_code="PERFORMANCE_CALC_ERROR",
            details={
                "metric": metric,
                "reason": reason,
                "input_data": input_data
            }
        )


# Utility Functions for Error Handling
def handle_database_error(e: Exception, operation: str, context: Dict[str, Any]) -> DatabaseError:
    """Convert generic database exceptions to specific error types."""
    error_msg = str(e).lower()
    
    if "connection" in error_msg or "timeout" in error_msg:
        return DatabaseConnectionError(
            connection_string=context.get("connection_string", "unknown"),
            reason=str(e)
        )
    elif "not found" in error_msg:
        if "investor" in error_msg:
            return InvestorNotFoundError(context.get("investor_code", "unknown"))
        elif "fund" in error_msg:
            return FundNotFoundError(context.get("fund_id", "unknown"))
    
    # Generic database error
    return DatabaseError(
        message=f"Database error during {operation}: {str(e)}",
        error_code="DB_GENERIC_ERROR",
        details={"operation": operation, "context": context}
    )


def handle_api_error(e: Exception, service: str, operation: str) -> APIError:
    """Convert generic API exceptions to specific error types."""
    error_msg = str(e).lower()
    
    if "openai" in service.lower():
        return OpenAIError(operation=operation, reason=str(e))
    elif "vector" in service.lower() or "chroma" in service.lower():
        return VectorStoreError(operation=operation, store_type=service, reason=str(e))
    
    # Generic API error
    return APIError(
        message=f"API error in {service} during {operation}: {str(e)}",
        error_code="API_GENERIC_ERROR",
        details={"service": service, "operation": operation}
    )


def log_error_with_context(logger, error: FOReportingError, additional_context: Optional[Dict] = None):
    """Log error with full context information."""
    log_data = {
        "error_type": error.__class__.__name__,
        "error_code": error.error_code,
        "message": error.message,
        "details": error.details
    }
    
    if additional_context:
        log_data["context"] = additional_context
    
    logger.error(f"Error occurred: {error.message}", extra=log_data)