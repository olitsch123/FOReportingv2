"""Capital Account Statement extractor with multi-method extraction."""

import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from .base import BaseExtractor, ExtractionResult, ExtractionMethod

logger = logging.getLogger(__name__)


class CapitalAccountExtractor(BaseExtractor):
    """Extract capital account fields with high accuracy."""
    
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define capital account fields with extraction patterns."""
        return {
            'beginning_balance': {
                'patterns': [
                    r'beginning\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'opening\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'balance[,\s]+beginning[\s:]+\$?([\d,]+\.?\d*)',
                    r'balance\s+at\s+beginning\s+of\s+period[\s:]+\$?([\d,]+\.?\d*)',
                    r'prior\s+period\s+ending\s+balance[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Beginning Balance', 'Opening Balance', 'Balance, Beginning', 'Prior Balance'],
                'type': 'decimal',
                'required': True
            },
            'ending_balance': {
                'patterns': [
                    r'ending\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'closing\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'balance[,\s]+ending[\s:]+\$?([\d,]+\.?\d*)',
                    r'nav[\s:]+\$?([\d,]+\.?\d*)',
                    r'net\s+asset\s+value[\s:]+\$?([\d,]+\.?\d*)',
                    r'partner[\'s]?\s+capital[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Ending Balance', 'NAV', 'Net Asset Value', 'Balance, Ending', 'Partner Capital'],
                'type': 'decimal',
                'required': True
            },
            'contributions_period': {
                'patterns': [
                    r'contributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'capital\s+calls?[\s:]+\$?([\d,]+\.?\d*)',
                    r'paid[\s-]in\s+capital[\s:]+\$?([\d,]+\.?\d*)',
                    r'additional\s+capital[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Contributions', 'Capital Calls', 'Paid-in Capital', 'Capital Contributions'],
                'type': 'decimal',
                'period_variants': ['Period', 'QTD', 'YTD', 'ITD']
            },
            'distributions_period': {
                'patterns': [
                    r'distributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'proceeds[\s:]+\$?([\d,]+\.?\d*)',
                    r'cash\s+distributions?[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Distributions', 'Cash Distributions', 'Proceeds', 'Total Distributions'],
                'type': 'decimal'
            },
            'distributions_roc_period': {
                'patterns': [
                    r'return\s+of\s+capital[\s:]+\$?([\d,]+\.?\d*)',
                    r'roc[\s:]+\$?([\d,]+\.?\d*)',
                    r'capital\s+return[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Return of Capital', 'ROC', 'Capital Return'],
                'type': 'decimal'
            },
            'distributions_gain_period': {
                'patterns': [
                    r'realized\s+gains?[\s:]+\$?([\d,]+\.?\d*)',
                    r'gains?\s+distributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'capital\s+gains?[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Realized Gains', 'Gains', 'Capital Gains', 'Gain Distributions'],
                'type': 'decimal'
            },
            'distributions_income_period': {
                'patterns': [
                    r'income\s+distributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'dividends?[\s:]+\$?([\d,]+\.?\d*)',
                    r'interest\s+income[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Income', 'Dividends', 'Interest', 'Income Distributions'],
                'type': 'decimal'
            },
            'management_fees_period': {
                'patterns': [
                    r'management\s+fees?[\s:]+\$?([\d,]+\.?\d*)',
                    r'mgmt\s+fees?[\s:]+\$?([\d,]+\.?\d*)',
                    r'advisory\s+fees?[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Management Fees', 'Mgmt Fees', 'Advisory Fees'],
                'type': 'decimal'
            },
            'partnership_expenses_period': {
                'patterns': [
                    r'partnership\s+expenses?[\s:]+\$?([\d,]+\.?\d*)',
                    r'fund\s+expenses?[\s:]+\$?([\d,]+\.?\d*)',
                    r'operating\s+expenses?[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Partnership Expenses', 'Fund Expenses', 'Operating Expenses'],
                'type': 'decimal'
            },
            'realized_gain_loss_period': {
                'patterns': [
                    r'realized\s+gain/?\(loss\)[\s:]+\$?([\d,\-\(\)]+\.?\d*)',
                    r'realized\s+g/?\(l\)[\s:]+\$?([\d,\-\(\)]+\.?\d*)',
                    r'net\s+realized[\s:]+\$?([\d,\-\(\)]+\.?\d*)'
                ],
                'table_headers': ['Realized Gain/(Loss)', 'Realized G/(L)', 'Net Realized'],
                'type': 'decimal'
            },
            'unrealized_gain_loss_period': {
                'patterns': [
                    r'unrealized\s+gain/?\(loss\)[\s:]+\$?([\d,\-\(\)]+\.?\d*)',
                    r'unrealized\s+g/?\(l\)[\s:]+\$?([\d,\-\(\)]+\.?\d*)',
                    r'change\s+in\s+unrealized[\s:]+\$?([\d,\-\(\)]+\.?\d*)'
                ],
                'table_headers': ['Unrealized Gain/(Loss)', 'Unrealized G/(L)', 'Change in Unrealized'],
                'type': 'decimal'
            },
            'total_commitment': {
                'patterns': [
                    r'total\s+commitment[\s:]+\$?([\d,]+\.?\d*)',
                    r'committed\s+capital[\s:]+\$?([\d,]+\.?\d*)',
                    r'commitment\s+amount[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Total Commitment', 'Committed Capital', 'Commitment'],
                'type': 'decimal'
            },
            'unfunded_commitment': {
                'patterns': [
                    r'unfunded\s+commitment[\s:]+\$?([\d,]+\.?\d*)',
                    r'remaining\s+commitment[\s:]+\$?([\d,]+\.?\d*)',
                    r'undrawn\s+commitment[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Unfunded Commitment', 'Remaining Commitment', 'Undrawn'],
                'type': 'decimal'
            },
            'ownership_pct': {
                'patterns': [
                    r'ownership\s+percentage[\s:]+(\d+\.?\d*)\s*%',
                    r'ownership[\s:]+(\d+\.?\d*)\s*%',
                    r'interest[\s:]+(\d+\.?\d*)\s*%'
                ],
                'table_headers': ['Ownership %', 'Interest %', 'Percentage Interest'],
                'type': 'percentage'
            }
        }
    
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract capital account fields using multiple methods."""
        extracted_data = {}
        extraction_audit = []
        
        # Extract each field using multiple methods
        for field_name, field_def in self.field_definitions.items():
            results = []
            
            # Method 1: Table extraction (highest confidence)
            if tables:
                table_result = self.extract_from_table(tables, field_name)
                if table_result:
                    results.append(table_result)
            
            # Method 2: Regex extraction
            regex_result = self.extract_with_regex(text, field_name)
            if regex_result:
                results.append(regex_result)
            
            # Method 3: Specialized extraction for complex fields
            if field_name in ['distributions_period', 'realized_gain_loss_period']:
                special_result = self._extract_complex_field(text, tables, field_name)
                if special_result:
                    results.append(special_result)
            
            # Reconcile results
            if results:
                best_result = self.reconcile_results(results)
                if best_result:
                    extracted_data[field_name] = best_result.value
                    
                    # Add to audit trail
                    extraction_audit.append({
                        'field': field_name,
                        'value': best_result.value,
                        'method': best_result.method,
                        'confidence': best_result.confidence,
                        'alternatives': best_result.alternatives
                    })
        
        # Add calculated fields
        extracted_data = self._add_calculated_fields(extracted_data)
        
        # Add metadata
        extracted_data['extraction_audit'] = extraction_audit
        extracted_data['extraction_timestamp'] = datetime.utcnow().isoformat()
        
        return extracted_data
    
    def _extract_complex_field(self, text: str, tables: List[Dict], field_name: str) -> Optional[ExtractionResult]:
        """Extract complex fields that may have multiple components."""
        if field_name == 'distributions_period':
            # Sum up all distribution components if broken down
            components = [
                'distributions_roc_period',
                'distributions_gain_period',
                'distributions_income_period',
                'distributions_tax_period'
            ]
            
            total = Decimal('0')
            found_components = []
            
            for component in components:
                result = self.extract_with_regex(text, component)
                if not result and tables:
                    result = self.extract_from_table(tables, component)
                
                if result and result.value:
                    total += Decimal(str(result.value))
                    found_components.append(component)
            
            if found_components:
                return ExtractionResult(
                    field_name=field_name,
                    value=total,
                    method=ExtractionMethod.REGEX,
                    confidence=0.85,
                    raw_text=f"Sum of {', '.join(found_components)}"
                )
        
        return None
    
    def _add_calculated_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add calculated fields based on extracted data."""
        # Calculate drawn commitment if we have total and unfunded
        if 'total_commitment' in data and 'unfunded_commitment' in data:
            data['drawn_commitment'] = (
                Decimal(str(data['total_commitment'])) - 
                Decimal(str(data['unfunded_commitment']))
            )
        
        # Calculate total activity
        activity_fields = [
            'contributions_period',
            'distributions_period',
            'management_fees_period',
            'partnership_expenses_period',
            'realized_gain_loss_period',
            'unrealized_gain_loss_period'
        ]
        
        if 'beginning_balance' in data and 'ending_balance' in data:
            # Calculate implied activity
            beginning = Decimal(str(data['beginning_balance']))
            ending = Decimal(str(data['ending_balance']))
            implied_activity = ending - beginning
            data['net_activity_period'] = implied_activity
        
        return data