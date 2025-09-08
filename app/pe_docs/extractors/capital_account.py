"""Capital Account Statement extractor with multi-method extraction."""

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base import BaseExtractor, ExtractionMethod, ExtractionResult

logger = logging.getLogger(__name__)


class CapitalAccountExtractor(BaseExtractor):
    """Extract capital account fields with high accuracy."""
    
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define capital account fields with extraction patterns."""
        return {
            'beginning_balance': {
                'patterns': [
                    r'beginning\s+balance[\s\(\):]+\$?([\d,]+\.?\d*)',
                    r'opening\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'balance[,\s]+beginning[\s:]+\$?([\d,]+\.?\d*)',
                    r'beginning\s+balance\s*\([^)]+\)[\s:]+\$?([\d,]+\.?\d*)',
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
                    r'total\s+contributions\s+this\s+period[\s:]+\$?([\d,]+\.?\d*)',
                    r'contributions\s+this\s+period[\s:]+\$?([\d,]+\.?\d*)',
                    r'capital\s+call\s+#\d+[^$]+\$?([\d,]+\.?\d*)',
                    r'contributions?[\s:]+\$?([\d,]+\.?\d*)(?=\s*\n)',
                    r'capital\s+calls?[\s:]+\$?([\d,]+\.?\d*)',
                    r'additional\s+capital[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Contributions', 'Capital Calls', 'Paid-in Capital', 'Capital Contributions'],
                'type': 'decimal',
                'period_variants': ['Period', 'QTD', 'YTD', 'ITD']
            },
            'distributions_period': {
                'patterns': [
                    r'total\s+distributions\s+this\s+period[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'distributions\s+this\s+period[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'distributions?[\s:]+\$?\(?([\d,]+\.?\d*)\)?(?=\s*\n)',
                    r'proceeds[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'cash\s+distributions?[\s:]+\$?\(?([\d,]+\.?\d*)\)?'
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
            'as_of_date': {
                'patterns': [
                    r'as\s+of\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                    r'statement\s+date[\s:]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                    r'reporting\s+date[\s:]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                    r'period\s+end(?:ing)?[\s:]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                    r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s+statement',
                    r'q[1-4]\s+(\d{4})',  # Q2 2025 format
                    r'quarter\s+end(?:ing)?\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
                    r'(\d{1,2}\.\d{1,2}\.\d{2,4})',  # German date format
                    r'(\d{4}-\d{1,2}-\d{1,2})'  # ISO date format
                ],
                'table_headers': ['As of Date', 'Statement Date', 'Reporting Date', 'Period End', 'Date'],
                'type': 'date',
                'required': True
            },
            'management_fees_period': {
                'patterns': [
                    r'q\d+\s+\d+\s+management\s+fee\s*\([^)]+\)[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'management\s+fee\s*\([^%]+%\)[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'management\s+fees?[\s:]+\$?\(?([\d,]+\.?\d*)\)?(?!\s*%)',
                    r'mgmt\s+fees?[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'advisory\s+fees?[\s:]+\$?\(?([\d,]+\.?\d*)\)?'
                ],
                'table_headers': ['Management Fees', 'Mgmt Fees', 'Advisory Fees'],
                'type': 'decimal'
            },
            'partnership_expenses_period': {
                'patterns': [
                    r'total\s+partnership\s+expenses[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'partnership\s+expenses?[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'fund\s+expenses?[\s:]+\$?\(?([\d,]+\.?\d*)\)?',
                    r'operating\s+expenses?[\s:]+\$?\(?([\d,]+\.?\d*)\)?'
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
            'drawn_commitment': {
                'patterns': [
                    r'drawn\s+commitment[\s:]+\$?([\d,]+\.?\d*)',
                    r'called\s+commitment[\s:]+\$?([\d,]+\.?\d*)',
                    r'paid[\s-]in\s+capital[\s:]+\$?([\d,]+\.?\d*)',
                    r'cumulative\s+contributions[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Drawn Commitment', 'Called Commitment', 'Paid-In Capital'],
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
            
            # Method 4: Date-specific extraction
            if field_name == 'as_of_date' and not results:
                date_result = self._extract_date_from_filename_and_text(text, field_name)
                if date_result:
                    results.append(date_result)
            
            # Reconcile results
            if results:
                best_result = self.reconcile_results(results)
                if best_result:
                    # Convert date strings to proper format
                    if field_def.get('type') == 'date' and best_result.value:
                        parsed_date = self._parse_date(best_result.value)
                        if parsed_date:
                            extracted_data[field_name] = parsed_date
                        else:
                            extracted_data[field_name] = best_result.value
                    else:
                        extracted_data[field_name] = best_result.value
                    
                    # Add to audit trail
                    extraction_audit.append({
                        'field': field_name,
                        'value': extracted_data[field_name],
                        'method': best_result.method,
                        'confidence': best_result.confidence,
                        'alternatives': best_result.alternatives
                    })
        
        # Fallback: If no as_of_date found, try to infer from Q2 2025 in filename
        if 'as_of_date' not in extracted_data or not extracted_data['as_of_date']:
            fallback_date = self._extract_date_from_context(text)
            if fallback_date:
                extracted_data['as_of_date'] = fallback_date
                extraction_audit.append({
                    'field': 'as_of_date',
                    'value': fallback_date,
                    'method': ExtractionMethod.POSITIONAL,
                    'confidence': 0.7,
                    'alternatives': []
                })
        
        # Add calculated fields
        extracted_data = self._add_calculated_fields(extracted_data)
        
        # Add metadata
        extracted_data['extraction_audit'] = extraction_audit
        extracted_data['extraction_timestamp'] = datetime.utcnow().isoformat()
        
        return extracted_data
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format."""
        if not date_str:
            return None
            
        try:
            from dateutil import parser

            # Handle Q2 2025 format
            if re.match(r'q[1-4]\s+\d{4}', date_str.lower()):
                quarter_match = re.search(r'q([1-4])\s+(\d{4})', date_str.lower())
                if quarter_match:
                    quarter, year = quarter_match.groups()
                    # Map quarter to end date
                    quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
                    return f"{year}-{quarter_ends[quarter]}"
            
            # Parse other date formats
            parsed = parser.parse(date_str)
            return parsed.strftime('%Y-%m-%d')
            
        except Exception as e:
            logger.warning(f"Could not parse date '{date_str}': {e}")
            return None
    
    def _extract_date_from_filename_and_text(self, text: str, field_name: str) -> Optional[ExtractionResult]:
        """Extract date from filename and text context."""
        # Look for Q2 2025 pattern in text
        quarter_patterns = [
            r'Q([1-4])\s+(\d{4})',
            r'quarter\s+([1-4])\s+(\d{4})',
            r'(\d{4})\s+Q([1-4])'
        ]
        
        for pattern in quarter_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    quarter, year = match.groups()
                    if quarter.isdigit() and year.isdigit():
                        quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
                        date_str = f"{year}-{quarter_ends.get(quarter, '12-31')}"
                        return ExtractionResult(
                            field_name=field_name,
                            value=date_str,
                            method=ExtractionMethod.REGEX,
                            confidence=0.8,
                            raw_text=match.group(0)
                        )
        
        return None
    
    def _extract_date_from_context(self, text: str) -> Optional[str]:
        """Extract date from context clues."""
        # Look for Q2 2025 in filename or text
        quarter_match = re.search(r'Q([1-4])\s+(\d{4})', text, re.IGNORECASE)
        if quarter_match:
            quarter, year = quarter_match.groups()
            quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
            return f"{year}-{quarter_ends[quarter]}"
        
        return None
    
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