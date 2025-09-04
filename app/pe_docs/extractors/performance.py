"""Performance metrics extractor for PE documents."""

from typing import Dict, Any, List
from .base import BaseExtractor

class PerformanceMetricsExtractor(BaseExtractor):
    """Extract performance metrics like IRR, MOIC, TVPI, etc."""
    
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define performance metric fields."""
        return {
            'irr_gross': {
                'patterns': [
                    r'gross\s+irr[\s:]+(\d+\.?\d*)\s*%',
                    r'irr\s+\(gross\)[\s:]+(\d+\.?\d*)\s*%'
                ],
                'table_headers': ['Gross IRR', 'IRR (Gross)'],
                'type': 'percentage'
            },
            'irr_net': {
                'patterns': [
                    r'net\s+irr[\s:]+(\d+\.?\d*)\s*%',
                    r'irr\s+\(net\)[\s:]+(\d+\.?\d*)\s*%'
                ],
                'table_headers': ['Net IRR', 'IRR (Net)'],
                'type': 'percentage'
            },
            'moic_gross': {
                'patterns': [
                    r'moic[\s:]+(\d+\.?\d*)x?',
                    r'multiple[\s:]+(\d+\.?\d*)x?'
                ],
                'table_headers': ['MOIC', 'Multiple'],
                'type': 'float'
            },
            'tvpi': {
                'patterns': [
                    r'tvpi[\s:]+(\d+\.?\d*)x?',
                    r'total\s+value[\s:]+(\d+\.?\d*)x?'
                ],
                'table_headers': ['TVPI', 'Total Value to Paid-In'],
                'type': 'float'
            },
            'dpi': {
                'patterns': [
                    r'dpi[\s:]+(\d+\.?\d*)x?',
                    r'distributed[\s:]+(\d+\.?\d*)x?'
                ],
                'table_headers': ['DPI', 'Distributed to Paid-In'],
                'type': 'float'
            },
            'rvpi': {
                'patterns': [
                    r'rvpi[\s:]+(\d+\.?\d*)x?',
                    r'residual[\s:]+(\d+\.?\d*)x?'
                ],
                'table_headers': ['RVPI', 'Residual Value to Paid-In'],
                'type': 'float'
            }
        }
    
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract performance metrics."""
        extracted_data = {}
        
        for field_name in self.field_definitions:
            # Try table extraction first
            result = self.extract_from_table(tables, field_name)
            if not result:
                result = self.extract_with_regex(text, field_name)
            
            if result:
                extracted_data[field_name] = result.value
        
        return extracted_data