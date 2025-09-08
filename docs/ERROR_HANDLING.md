# Error Handling Guide

## Overview

FOReporting v2 implements a comprehensive error handling system with custom exception classes, structured logging, and appropriate HTTP status codes.

## Custom Exception Hierarchy

### Base Exception
- `FOReportingError` - Base class for all application errors
  - Includes error code, message, and details dictionary
  - Provides `to_dict()` method for API responses

### Document Processing Exceptions
- `DocumentProcessingError` - Base for document processing errors
- `DocumentNotFoundError` - Document file not found (404)
- `ProcessorNotAvailableError` - No processor for file type (422)
- `ExtractionError` - Data extraction failed (422)
- `ValidationError` - Data validation failed (422)

### Database Exceptions
- `DatabaseError` - Base for database errors
- `InvestorNotFoundError` - Investor not found (404)
- `FundNotFoundError` - Fund not found (404)
- `DatabaseConnectionError` - Connection failed (503)

### API and External Service Exceptions
- `APIError` - Base for external API errors
- `OpenAIError` - OpenAI API errors (503)
- `VectorStoreError` - Vector store errors (503)
- `FileWatcherError` - File watcher errors (500)

### Configuration Exceptions
- `ConfigurationError` - Configuration errors (500)
- `DependencyError` - Missing dependencies (500)

### PE-Specific Exceptions
- `PEExtractionError` - PE document extraction errors
- `ReconciliationError` - Data reconciliation errors (409)
- `PerformanceCalculationError` - Performance metric errors (422)

## Usage Examples

### Basic Exception Handling
```python
from app.exceptions import DocumentNotFoundError, ExtractionError

try:
    document = process_document(file_path)
except FileNotFoundError:
    raise DocumentNotFoundError(file_path, {"reason": "File not accessible"})
except Exception as e:
    raise ExtractionError(file_path, "openai", str(e))
```

### Database Error Handling
```python
from app.exceptions import handle_database_error

try:
    investor = db.query(Investor).filter_by(code=code).first()
    if not investor:
        raise InvestorNotFoundError(code)
except SQLAlchemyError as e:
    raise handle_database_error(e, "get_investor", {"investor_code": code})
```

### API Error Handling
```python
from app.exceptions import OpenAIError

try:
    response = openai_client.chat.completions.create(...)
except openai.APIError as e:
    raise OpenAIError("document_extraction", str(e), {"model": "gpt-4"})
```

## Error Response Format

All errors return a consistent JSON structure:

```json
{
  "error": {
    "error_type": "DocumentNotFoundError",
    "message": "Document not found: /path/to/file.pdf",
    "error_code": "DOC_NOT_FOUND",
    "details": {
      "file_path": "/path/to/file.pdf",
      "timestamp": 1640995200
    },
    "request_id": "uuid-here",
    "timestamp": 1640995200
  }
}
```

## HTTP Status Code Mapping

| Exception Type | HTTP Status | Description |
|---|---|---|
| DocumentNotFoundError | 404 | Resource not found |
| InvestorNotFoundError | 404 | Resource not found |
| FundNotFoundError | 404 | Resource not found |
| ProcessorNotAvailableError | 422 | Unprocessable entity |
| ValidationError | 422 | Validation failed |
| ExtractionError | 422 | Processing failed |
| ReconciliationError | 409 | Data conflict |
| DatabaseConnectionError | 503 | Service unavailable |
| OpenAIError | 503 | External service error |
| VectorStoreError | 503 | External service error |
| ConfigurationError | 500 | Internal server error |
| FileWatcherError | 500 | Internal server error |

## Logging Integration

All custom exceptions are automatically logged with structured data:

```python
logger.error(
    "forreporting_error",
    request_id=request_id,
    error_type="DocumentNotFoundError",
    error_code="DOC_NOT_FOUND",
    message="Document not found: /path/to/file.pdf",
    details={"file_path": "/path/to/file.pdf"},
    process_time=0.123
)
```

## Best Practices

### 1. Use Specific Exceptions
```python
# Good
raise DocumentNotFoundError(file_path)

# Bad  
raise Exception("Document not found")
```

### 2. Include Context in Details
```python
raise ExtractionError(
    file_path=file_path,
    extraction_method="openai",
    reason="API rate limit exceeded"
)
```

### 3. Chain Exceptions Appropriately
```python
try:
    process_document()
except OpenAIError as e:
    raise ExtractionError(file_path, "openai", str(e)) from e
```

### 4. Log with Context
```python
from app.exceptions import log_error_with_context

try:
    risky_operation()
except FOReportingError as e:
    log_error_with_context(logger, e, {"user_id": user_id, "operation": "extract"})
    raise
```

## Error Recovery

### Automatic Retry
For transient errors (OpenAI rate limits, network issues):
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def extract_with_retry():
    try:
        return await extract_data()
    except OpenAIError as e:
        if "rate_limit" in str(e):
            raise  # Will be retried
        else:
            raise ExtractionError("openai", "non_retryable", str(e))
```

### Graceful Degradation
```python
try:
    enhanced_extraction = await openai_extract()
except OpenAIError:
    logger.warning("OpenAI unavailable, falling back to regex extraction")
    basic_extraction = regex_extract()
```

## Monitoring Integration

Custom exceptions integrate with monitoring systems:
- Prometheus metrics for error rates by type
- Structured logs for error analysis
- Request IDs for distributed tracing
- Error details for debugging

## Testing Error Handling

```python
import pytest
from app.exceptions import DocumentNotFoundError

def test_document_not_found_error():
    with pytest.raises(DocumentNotFoundError) as exc_info:
        raise DocumentNotFoundError("/missing/file.pdf")
    
    error = exc_info.value
    assert error.error_code == "DOC_NOT_FOUND"
    assert "/missing/file.pdf" in error.message
    assert "file_path" in error.details
```