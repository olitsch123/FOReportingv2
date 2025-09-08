"""Commitment extractor for subscription documents."""

from typing import Any, Dict, List

from .base import BaseExtractor


class CommitmentExtractor(BaseExtractor):
    """Extract commitment information from subscription agreements."""
    
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define commitment fields."""
        return {
            'commitment_amount': {
                'patterns': [
                    r'commitment\s+amount[\s:]+\$?([\d,]+\.?\d*)',
                    r'subscription\s+amount[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Commitment Amount', 'Subscription Amount'],
                'type': 'decimal'
            },
            'commitment_date': {
                'patterns': [
                    r'commitment\s+date[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'subscription\s+date[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                ],
                'table_headers': ['Commitment Date', 'Subscription Date'],
                'type': 'date'
            },
            'management_fee_rate': {
                'patterns': [
                    r'management\s+fee[\s:]+(\d+\.?\d*)\s*%',
                    r'mgmt\s+fee[\s:]+(\d+\.?\d*)\s*%'
                ],
                'table_headers': ['Management Fee', 'Mgmt Fee %'],
                'type': 'percentage'
            },
            'carried_interest_rate': {
                'patterns': [
                    r'carried\s+interest[\s:]+(\d+\.?\d*)\s*%',
                    r'carry[\s:]+(\d+\.?\d*)\s*%'
                ],
                'table_headers': ['Carried Interest', 'Carry %'],
                'type': 'percentage'
            }
        }
    
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract commitment data."""
        extracted_data = {}
        
        for field_name in self.field_definitions:
            # Try table extraction first
            result = self.extract_from_table(tables, field_name)
            if not result:
                result = self.extract_with_regex(text, field_name)
            
            if result:
                extracted_data[field_name] = result.value
        
        return extracted_data