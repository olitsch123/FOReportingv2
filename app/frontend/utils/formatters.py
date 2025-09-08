"""Data formatting utilities for the frontend."""

from datetime import datetime
from typing import Any, Optional, Union
import pandas as pd


def format_currency(
    value: Optional[Union[int, float]], 
    currency: str = "EUR", 
    decimal_places: int = 0
) -> str:
    """Format currency values for display."""
    if value is None:
        return "—"
    
    try:
        # Handle different currency symbols
        symbols = {
            "EUR": "€",
            "USD": "$", 
            "GBP": "£"
        }
        symbol = symbols.get(currency, currency)
        
        if decimal_places == 0:
            return f"{symbol}{value:,.0f}"
        else:
            return f"{symbol}{value:,.{decimal_places}f}"
            
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: Optional[Union[int, float]], decimal_places: int = 1) -> str:
    """Format percentage values for display."""
    if value is None:
        return "—"
    
    try:
        return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return str(value)


def format_multiple(value: Optional[Union[int, float]], decimal_places: int = 2) -> str:
    """Format multiple values (MOIC, TVPI, etc.) for display."""
    if value is None:
        return "—"
    
    try:
        return f"{value:.{decimal_places}f}x"
    except (ValueError, TypeError):
        return str(value)


def format_date(value: Optional[Union[str, datetime]], format_str: str = "%Y-%m-%d") -> str:
    """Format date values for display."""
    if value is None:
        return "—"
    
    try:
        if isinstance(value, str):
            # Try to parse string date
            if "T" in value:  # ISO format
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(value, "%Y-%m-%d")
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)
        
        return dt.strftime(format_str)
        
    except (ValueError, TypeError):
        return str(value)


def format_file_size(size_bytes: Optional[int]) -> str:
    """Format file size in human-readable format."""
    if size_bytes is None:
        return "—"
    
    try:
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
        
    except (ValueError, TypeError):
        return str(size_bytes)


def format_processing_status(status: Optional[str]) -> tuple[str, str]:
    """Format processing status with appropriate icon and color."""
    if not status:
        return "❓", "Unknown"
    
    status_map = {
        "completed": ("✅", "Completed"),
        "processing": ("🔄", "Processing"),
        "pending": ("⏳", "Pending"),
        "failed": ("❌", "Failed"),
        "skipped": ("⏭️", "Skipped")
    }
    
    return status_map.get(status.lower(), ("❓", status.title()))


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safely divide two numbers, returning None if invalid."""
    try:
        if numerator is None or denominator is None or denominator == 0:
            return None
        return float(numerator) / float(denominator)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def create_summary_stats(data: list) -> dict:
    """Create summary statistics from a list of data."""
    if not data:
        return {"count": 0, "total": 0, "average": 0}
    
    try:
        df = pd.DataFrame(data)
        numeric_cols = df.select_dtypes(include=['number']).columns
        
        stats = {
            "count": len(data),
            "numeric_columns": len(numeric_cols)
        }
        
        for col in numeric_cols:
            stats[f"{col}_sum"] = df[col].sum()
            stats[f"{col}_mean"] = df[col].mean()
            stats[f"{col}_min"] = df[col].min()
            stats[f"{col}_max"] = df[col].max()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error creating summary stats: {e}")
        return {"count": len(data), "error": str(e)}


def truncate_text(text: Optional[str], max_length: int = 100) -> str:
    """Truncate text for display with ellipsis."""
    if not text:
        return "—"
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."