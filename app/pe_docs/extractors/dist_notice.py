"""Distribution Notice extractor."""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re

class DistNoticeExtractor:
    """Extract data from Distribution Notices."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract single cashflow from distribution notice.
        """
        result = {
            'cashflows': []
        }
        
        text = parsed_data.get('text', '')
        tables = parsed_data.get('tables', [])
        
        # Extract distribution details
        dist_data = self._extract_distribution_details(text, tables)
        
        if dist_data:
            cashflow = {
                'flow_type': 'DIST',
                'amount': dist_data['amount'],
                'flow_date': dist_data['dist_date'],
                'payment_date': dist_data.get('payment_date'),
                'fund_id': doc_metadata.get('fund_id'),
                'investor_id': doc_metadata.get('investor_id'),
                'doc_id': doc_metadata.get('doc_id'),
                'source_trace': {
                    'extraction_method': 'distribution_notice',
                    'doc_type': 'DIST',
                    'confidence': dist_data.get('confidence', 0.8)
                }
            }
            result['cashflows'].append(cashflow)
        
        return result
    
    def _extract_distribution_details(self, text: str, tables: List[Dict]) -> Optional[Dict[str, Any]]:
        """Extract distribution amount, date, and payment date."""
        dist_data = {}
        
        # Amount patterns
        amount_patterns = [
            r'distribution amount[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'total distribution[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'amount payable[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'net distribution[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1).replace(',', ''))
                    dist_data['amount'] = amount
                    break
                except ValueError:
                    continue
        
        # Date patterns
        date_patterns = [
            r'distribution date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'payment date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'effective date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                parsed_date = self._parse_date(match)
                if parsed_date:
                    dates_found.append(parsed_date)
        
        # Assign dates
        if dates_found:
            dates_found.sort()
            dist_data['dist_date'] = dates_found[0]
            if len(dates_found) > 1:
                dist_data['payment_date'] = dates_found[-1]
        
        # Extract from tables if text extraction failed
        if not dist_data.get('amount') or not dist_data.get('dist_date'):
            table_data = self._extract_from_tables(tables)
            dist_data.update(table_data)
        
        # Validation
        if dist_data.get('amount') and dist_data.get('dist_date'):
            dist_data['confidence'] = 0.9
            return dist_data
        
        return None
    
    def _extract_from_tables(self, tables: List[Dict]) -> Dict[str, Any]:
        """Extract distribution details from tables."""
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
                if any(term in header_lower for term in ['amount', 'distribution', 'total']):
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
                    dist_date = self._parse_date(str(row[date_col]))
                    if dist_date:
                        result['dist_date'] = dist_date
        
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
dist_notice_extractor = DistNoticeExtractor()