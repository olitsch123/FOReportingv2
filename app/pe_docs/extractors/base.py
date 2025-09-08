"""Base classes for PE document extraction."""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from app.pe_docs.config import get_pe_config

logger = logging.getLogger(__name__)
pe_config = get_pe_config()


class ExtractionMethod(str, Enum):
    """Extraction method used."""
    TABLE = "table"
    REGEX = "regex"
    LLM = "llm"
    POSITIONAL = "positional"
    MANUAL = "manual"


@dataclass
class ExtractionResult:
    """Result of an extraction attempt."""
    field_name: str
    value: Any
    method: ExtractionMethod
    confidence: float
    raw_text: Optional[str] = None
    position: Optional[Dict[str, Any]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None


class BaseExtractor(ABC):
    """Base class for all PE document extractors."""
    
    def __init__(self):
        """Initialize extractor with field definitions."""
        self.field_definitions = self._get_field_definitions()
        self.regex_bank = pe_config.regex_bank
        self.phrase_bank = pe_config.phrase_bank
    
    @abstractmethod
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get field definitions for this extractor."""
        pass
    
    @abstractmethod
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract fields from document."""
        pass
    
    def extract_with_regex(self, text: str, field_name: str) -> Optional[ExtractionResult]:
        """Extract field using regex patterns."""
        field_def = self.field_definitions.get(field_name, {})
        patterns = field_def.get('patterns', [])
        
        for pattern in patterns:
            try:
                # Handle case-insensitive matching
                flags = re.IGNORECASE if field_def.get('case_insensitive', True) else 0
                match = re.search(pattern, text, flags)
                
                if match:
                    # Extract value from match groups
                    value = match.group(1) if match.groups() else match.group(0)
                    
                    # Clean and convert value
                    value = self._clean_value(value, field_def.get('type', 'string'))
                    
                    return ExtractionResult(
                        field_name=field_name,
                        value=value,
                        method=ExtractionMethod.REGEX,
                        confidence=0.8,
                        raw_text=match.group(0),
                        position={'start': match.start(), 'end': match.end()}
                    )
            except Exception as e:
                logger.warning(f"Regex extraction error for {field_name}: {e}")
        
        return None
    
    def extract_from_table(self, tables: List[Dict], field_name: str) -> Optional[ExtractionResult]:
        """Extract field from table data."""
        field_def = self.field_definitions.get(field_name, {})
        headers = field_def.get('table_headers', [])
        
        for table in tables:
            # Check if table has relevant headers
            table_headers = table.get('headers', [])
            
            for header in headers:
                header_lower = header.lower()
                
                # Find matching column
                col_idx = None
                for idx, th in enumerate(table_headers):
                    if header_lower in str(th).lower():
                        col_idx = idx
                        break
                
                if col_idx is not None:
                    # Extract value from table
                    rows = table.get('rows', [])
                    for row in rows:
                        if len(row) > col_idx:
                            value = row[col_idx]
                            if value and str(value).strip():
                                # Clean and convert value
                                value = self._clean_value(value, field_def.get('type', 'string'))
                                
                                return ExtractionResult(
                                    field_name=field_name,
                                    value=value,
                                    method=ExtractionMethod.TABLE,
                                    confidence=0.9,
                                    raw_text=str(value)
                                )
        
        return None
    
    def _clean_value(self, value: Any, field_type: str) -> Any:
        """Clean and convert extracted value based on field type."""
        if value is None:
            return None
        
        # Convert to string for processing
        value_str = str(value).strip()
        
        # Remove common formatting
        value_str = value_str.replace('$', '').replace('€', '').replace('£', '')
        value_str = value_str.replace(',', '').replace(' ', '')
        value_str = value_str.replace('(', '-').replace(')', '')  # Handle negative numbers
        
        # Convert based on type
        try:
            if field_type == 'decimal' or field_type == 'money':
                # Handle percentages
                if value_str.endswith('%'):
                    return Decimal(value_str[:-1]) / 100
                return Decimal(value_str) if value_str else Decimal('0')
            
            elif field_type == 'integer':
                return int(float(value_str)) if value_str else 0
            
            elif field_type == 'float':
                return float(value_str) if value_str else 0.0
            
            elif field_type == 'percentage':
                if value_str.endswith('%'):
                    value_str = value_str[:-1]
                return Decimal(value_str) / 100 if value_str else Decimal('0')
            
            elif field_type == 'date':
                # Simple date parsing - enhance as needed
                from dateutil import parser
                return parser.parse(value_str).date()
            
            else:  # string
                return value_str
                
        except Exception as e:
            logger.warning(f"Value conversion error for {value_str}: {e}")
            return value_str
    
    def calculate_field_confidence(self, results: List[ExtractionResult]) -> float:
        """Calculate overall confidence for a field based on multiple extraction results."""
        if not results:
            return 0.0
        
        # Weight by method reliability
        method_weights = {
            ExtractionMethod.TABLE: 0.9,
            ExtractionMethod.REGEX: 0.8,
            ExtractionMethod.POSITIONAL: 0.7,
            ExtractionMethod.LLM: 0.7,
            ExtractionMethod.MANUAL: 1.0
        }
        
        total_weight = 0
        weighted_sum = 0
        
        for result in results:
            weight = method_weights.get(result.method, 0.5)
            weighted_sum += result.confidence * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def reconcile_results(self, results: List[ExtractionResult]) -> Optional[ExtractionResult]:
        """Reconcile multiple extraction results for the same field."""
        if not results:
            return None
        
        if len(results) == 1:
            return results[0]
        
        # Group by value
        value_groups = {}
        for result in results:
            value_key = str(result.value)
            if value_key not in value_groups:
                value_groups[value_key] = []
            value_groups[value_key].append(result)
        
        # Score each value group
        best_score = 0
        best_result = None
        
        for value_key, group in value_groups.items():
            # Calculate group score
            score = sum(r.confidence for r in group) / len(results)
            score *= len(group) / len(results)  # Consensus bonus
            
            if score > best_score:
                best_score = score
                # Use highest confidence result from group
                best_result = max(group, key=lambda r: r.confidence)
                best_result.confidence = score
                best_result.alternatives = [
                    {'value': k, 'count': len(v), 'methods': [r.method for r in v]}
                    for k, v in value_groups.items() if k != value_key
                ]
        
        return best_result