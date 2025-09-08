"""Input validation and sanitization for FOReporting v2."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, field_validator


class FilePathValidator(BaseModel):
    """Validate and sanitize file paths."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    file_path: str
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path for security and existence."""
        if not v:
            raise ValueError("File path cannot be empty")
        
        # Prevent path traversal attacks
        if any(pattern in v for pattern in ['..', '~', '$', '|', ';', '&', '>', '<']):
            raise ValueError("Invalid characters in file path")
        
        # Convert to Path object and resolve
        path = Path(v)
        
        # Check if path exists
        if not path.exists():
            raise ValueError(f"File not found: {v}")
        
        # Check if it's a file (not directory)
        if not path.is_file():
            raise ValueError(f"Path is not a file: {v}")
        
        # Check file size (max 500MB)
        if path.stat().st_size > 500 * 1024 * 1024:
            raise ValueError("File too large (max 500MB)")
        
        return str(path.resolve())


class InvestorCodeValidator(BaseModel):
    """Validate investor codes."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    investor_code: str
    
    @field_validator('investor_code')
    @classmethod
    def validate_investor_code(cls, v: str) -> str:
        """Validate investor code format."""
        if not v:
            raise ValueError("Investor code cannot be empty")
        
        # Only allow alphanumeric and underscore
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Investor code can only contain letters, numbers, underscore and hyphen")
        
        # Length check
        if len(v) < 2 or len(v) > 50:
            raise ValueError("Investor code must be between 2 and 50 characters")
        
        return v.lower()


class DocumentTypeValidator(BaseModel):
    """Validate document types."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    document_type: str
    
    @field_validator('document_type')
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Validate document type against allowed values."""
        allowed_types = [
            "quarterly_report", "annual_report", "financial_statement",
            "investment_report", "portfolio_summary", "transaction_data",
            "benchmark_data", "qr", "ar", "cas", "call", "dist", 
            "lpa", "ppm", "subscription", "other"
        ]
        
        if v.lower() not in allowed_types:
            raise ValueError(f"Invalid document type. Allowed: {', '.join(allowed_types)}")
        
        return v.lower()


class DateRangeValidator(BaseModel):
    """Validate date ranges."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format."""
        if not v:
            return v
        
        # Check format YYYY-MM-DD
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        
        return v


class PaginationValidator(BaseModel):
    """Validate pagination parameters."""
    
    limit: int = 50
    offset: int = 0
    
    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit parameter."""
        if v < 1:
            raise ValueError("Limit must be at least 1")
        if v > 1000:
            raise ValueError("Limit cannot exceed 1000")
        return v
    
    @field_validator('offset')
    @classmethod
    def validate_offset(cls, v: int) -> int:
        """Validate offset parameter."""
        if v < 0:
            raise ValueError("Offset cannot be negative")
        return v


class ChatMessageValidator(BaseModel):
    """Validate chat messages."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    message: str
    session_id: Optional[str] = None
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate chat message."""
        if not v:
            raise ValueError("Message cannot be empty")
        
        # Length check
        if len(v) > 10000:
            raise ValueError("Message too long (max 10000 characters)")
        
        # Basic XSS prevention (remove script tags)
        v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
        v = re.sub(r'<iframe[^>]*>.*?</iframe>', '', v, flags=re.IGNORECASE | re.DOTALL)
        
        return v
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate session ID format."""
        if not v:
            return v
        
        # UUID format check
        if not re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', v):
            raise ValueError("Invalid session ID format")
        
        return v


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Replace unsafe characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]
    
    return name + ext


def validate_json_structure(data: Dict[str, Any], required_fields: List[str]) -> None:
    """Validate JSON structure has required fields."""
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing_fields)}"
        )


def validate_financial_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize financial metrics."""
    validated = {}
    
    # Define valid metric names and their constraints
    metric_constraints = {
        "nav": {"min": 0, "max": 1e12},
        "nav_per_share": {"min": 0, "max": 1e9},
        "total_value": {"min": 0, "max": 1e12},
        "committed_capital": {"min": 0, "max": 1e12},
        "drawn_capital": {"min": 0, "max": 1e12},
        "distributed_capital": {"min": 0, "max": 1e12},
        "unrealized_value": {"min": -1e12, "max": 1e12},
        "realized_value": {"min": -1e12, "max": 1e12},
        "irr": {"min": -1, "max": 10},  # -100% to 1000%
        "moic": {"min": 0, "max": 100},
        "dpi": {"min": 0, "max": 100},
        "rvpi": {"min": 0, "max": 100},
        "tvpi": {"min": 0, "max": 100}
    }
    
    for metric, value in metrics.items():
        if metric in metric_constraints:
            try:
                val = float(value)
                constraints = metric_constraints[metric]
                
                if val < constraints["min"] or val > constraints["max"]:
                    raise ValueError(f"{metric} value {val} out of range")
                
                validated[metric] = val
            except (TypeError, ValueError) as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid value for {metric}: {str(e)}"
                )
    
    return validated