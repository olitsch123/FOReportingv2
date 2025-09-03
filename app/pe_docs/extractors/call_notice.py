"""Capital Call Notice extractor."""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re

class CallNoticeExtractor:
    """Extract data from Capital Call Notices."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract single cashflow from call notice.
        """
        result = {
            'cashflows': []
        }
        
        text = parsed_data.get('text', '')
        tables = parsed_data.get('tables', [])
        
        # Extract call amount and date
        call_data = self._extract_call_details(text, tables)
        
        if call_data:
            cashflow = {
                'flow_type': 'CALL',
                'amount': call_data['amount'],
                'flow_date': call_data['call_date'],
                'due_date': call_data.get('due_date'),
                'fund_id': doc_metadata.get('fund_id'),
                'investor_id': doc_metadata.get('investor_id'),
                'doc_id': doc_metadata.get('doc_id'),
                'source_trace': {
                    'extraction_method': 'call_notice',
                    'doc_type': 'CALL',
                    'confidence': call_data.get('confidence', 0.8)
                }
            }
            result['cashflows'].append(cashflow)
        
        return result
    
    def _extract_call_details(self, text: str, tables: List[Dict]) -> Optional[Dict[str, Any]]:
        """Extract call amount, date, and due date."""
        call_data = {}
        
        # Amount patterns
        amount_patterns = [
            r'call amount[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'capital call[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'amount due[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'total amount[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1).replace(',', ''))
                    call_data['amount'] = amount
                    break
                except ValueError:
                    continue
        
        # Date patterns
        date_patterns = [
            r'call date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'effective date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'due date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                parsed_date = self._parse_date(match)
                if parsed_date:
                    dates_found.append(parsed_date)
        
        # Assign dates (call date is typically the first/earliest)
        if dates_found:
            dates_found.sort()
            call_data['call_date'] = dates_found[0]
            if len(dates_found) > 1:
                call_data['due_date'] = dates_found[-1]  # Latest is due date
        
        # Extract from tables if text extraction failed
        if not call_data.get('amount') or not call_data.get('call_date'):
            table_data = self._extract_from_tables(tables)
            call_data.update(table_data)
        
        # Validation
        if call_data.get('amount') and call_data.get('call_date'):
            call_data['confidence'] = 0.9
            return call_data
        
        return None
    
    def _extract_from_tables(self, tables: List[Dict]) -> Dict[str, Any]:
        """Extract call details from tables."""
        result = {}
        
        for table in tables:
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            if not headers or not rows:
                continue
            
            # Find amount and date columns
            amount_col = None
            date_col = None
            
            for idx, header in enumerate(headers):
                header_lower = str(header).lower()
                if any(term in header_lower for term in ['amount', 'call', 'total']):
                    amount_col = idx
                elif 'date' in header_lower:
                    date_col = idx
            
            # Extract from first data row
            if rows and amount_col is not None:
                row = rows[0]
                if len(row) > amount_col:
                    try:
                        amount_str = str(row[amount_col]).replace(',', '').replace('$', '').replace('€', '')
                        amount = float(amount_str)
                        result['amount'] = amount
                    except (ValueError, TypeError):
                        pass
                
                if date_col is not None and len(row) > date_col:
                    call_date = self._parse_date(str(row[date_col]))
                    if call_date:
                        result['call_date'] = call_date
        
        return result
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        if not date_str or str(date_str).strip() in ['', 'nan', 'None']:
            return None
        
        date_str = str(date_str).strip()
        
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y', 
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None

# Global extractor instance
call_notice_extractor = CallNoticeExtractor()