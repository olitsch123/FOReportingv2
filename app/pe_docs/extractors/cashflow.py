"""Cashflow extractor for capital calls and distributions."""

from typing import Dict, Any, List
from .base import BaseExtractor

class CashflowExtractor(BaseExtractor):
    """Extract cashflow information from capital calls and distribution notices."""
    
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define cashflow fields."""
        return {
            'call_amount': {
                'patterns': [
                    r'call\s+amount[\s:]+\$?([\d,]+\.?\d*)',
                    r'contribution\s+amount[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Call Amount', 'Contribution Amount'],
                'type': 'decimal'
            },
            'distribution_amount': {
                'patterns': [
                    r'distribution\s+amount[\s:]+\$?([\d,]+\.?\d*)',
                    r'proceeds[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Distribution Amount', 'Proceeds'],
                'type': 'decimal'
            },
            'due_date': {
                'patterns': [
                    r'due\s+date[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'payment\s+due[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                ],
                'table_headers': ['Due Date', 'Payment Due'],
                'type': 'date'
            },
            'payment_date': {
                'patterns': [
                    r'payment\s+date[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'distribution\s+date[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                ],
                'table_headers': ['Payment Date', 'Distribution Date'],
                'type': 'date'
            }
        }
    
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract cashflow data."""
        extracted_data = {}
        
        for field_name in self.field_definitions:
            # Try table extraction first
            result = self.extract_from_table(tables, field_name)
            if not result:
                result = self.extract_with_regex(text, field_name)
            
            if result:
                extracted_data[field_name] = result.value
        
        return extracted_data