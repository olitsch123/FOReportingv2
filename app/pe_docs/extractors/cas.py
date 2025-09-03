"""Capital Account Statement extractor."""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re
from ..config import field_library

class CASExtractor:
    """Extract data from Capital Account Statements."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract cashflows and NAV observations from CAS.
        """
        result = {
            'nav_observations': [],
            'cashflows': [],
            'period_rollup': {}
        }
        
        text = parsed_data.get('text', '')
        tables = parsed_data.get('tables', [])
        
        # Extract from structured Excel data if available
        if 'structured_data' in parsed_data:
            result.update(self._extract_from_excel(parsed_data['structured_data'], doc_metadata))
        else:
            # Extract from PDF text and tables
            result.update(self._extract_from_pdf(text, tables, doc_metadata))
        
        return result
    
    def _extract_from_excel(self, structured_data: Dict[str, Any], doc_metadata: Dict) -> Dict[str, Any]:
        """Extract from Excel structured data."""
        result = {
            'nav_observations': [],
            'cashflows': [],
            'period_rollup': {}
        }
        
        # Look for capital account tabs
        cas_tabs = structured_data.get('capital_account', []) + structured_data.get('cashflows', [])
        
        for tab in cas_tabs:
            mapped_cols = tab.get('mapped_columns', {})
            headers = tab.get('headers', [])
            data_rows = tab.get('data', [])
            
            # Find relevant columns
            col_mapping = self._map_cas_columns(headers, mapped_cols)
            
            # Extract data from rows
            for row_idx, row in enumerate(data_rows):
                if len(row) <= max(col_mapping.values(), default=0):
                    continue
                
                # Extract cashflow if we have flow data
                cashflow = self._extract_cashflow_from_row(row, col_mapping, doc_metadata)
                if cashflow:
                    result['cashflows'].append(cashflow)
                
                # Extract NAV observation if we have NAV data
                nav_obs = self._extract_nav_from_row(row, col_mapping, doc_metadata)
                if nav_obs:
                    result['nav_observations'].append(nav_obs)
        
        return result
    
    def _extract_from_pdf(self, text: str, tables: List[Dict], doc_metadata: Dict) -> Dict[str, Any]:
        """Extract from PDF text and tables."""
        result = {
            'nav_observations': [],
            'cashflows': [],
            'period_rollup': {}
        }
        
        # Extract period rollup from text
        rollup = self._extract_period_rollup(text)
        if rollup:
            result['period_rollup'] = rollup
            
            # Create NAV observation from rollup
            if rollup.get('ending_balance') and rollup.get('as_of_date'):
                nav_obs = {
                    'nav': rollup['ending_balance'],
                    'as_of_date': rollup['as_of_date'],
                    'statement_date': rollup.get('statement_date', rollup['as_of_date']),
                    'coverage_start': rollup.get('period_start'),
                    'coverage_end': rollup.get('period_end', rollup['as_of_date']),
                    'scope': 'INVESTOR',  # CAS is investor-specific
                    'investor_id': doc_metadata.get('investor_id'),
                    'scenario': 'AS_REPORTED',
                    'version_no': 1,
                    'source_trace': {
                        'extraction_method': 'cas_period_rollup',
                        'doc_type': 'CAS'
                    }
                }
                result['nav_observations'].append(nav_obs)
        
        # Extract individual cashflows from tables
        for table in tables:
            cashflows = self._extract_cashflows_from_table(table, doc_metadata)
            result['cashflows'].extend(cashflows)
        
        return result
    
    def _map_cas_columns(self, headers: List[str], mapped_cols: Dict[int, str]) -> Dict[str, int]:
        """Map CAS-specific columns."""
        col_mapping = {}
        
        # Key CAS fields
        cas_fields = {
            'beginning_balance': ['beginning', 'opening', 'start'],
            'contributions': ['contribution', 'capital call', 'paid in'],
            'distributions': ['distribution', 'payout', 'return'],
            'fees': ['fee', 'management fee', 'expense'],
            'pnl': ['pnl', 'gain', 'loss', 'change', 'unrealized'],
            'ending_balance': ['ending', 'closing', 'balance'],
            'date': ['date', 'as of', 'period']
        }
        
        for idx, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            
            # Check mapped columns first
            if idx in mapped_cols:
                canonical = mapped_cols[idx]
                for field_key, keywords in cas_fields.items():
                    if any(kw in canonical.lower() for kw in keywords):
                        col_mapping[field_key] = idx
                        break
            
            # Fallback to header matching
            for field_key, keywords in cas_fields.items():
                if any(kw in header_lower for kw in keywords):
                    col_mapping[field_key] = idx
                    break
        
        return col_mapping
    
    def _extract_cashflow_from_row(self, row: List, col_mapping: Dict[str, int], doc_metadata: Dict) -> Optional[Dict[str, Any]]:
        """Extract cashflow from a data row."""
        cashflow = {}
        
        # Extract date
        if 'date' in col_mapping:
            date_val = self._parse_date(str(row[col_mapping['date']]))
            if date_val:
                cashflow['flow_date'] = date_val
        
        # Extract amounts
        amount_fields = ['contributions', 'distributions', 'fees']
        total_amount = 0
        flow_type = None
        
        for field in amount_fields:
            if field in col_mapping:
                try:
                    amount_str = str(row[col_mapping[field]]).replace(',', '').replace('$', '').replace('€', '')
                    amount = float(amount_str)
                    if amount != 0:
                        total_amount += amount
                        if field == 'contributions':
                            flow_type = 'CALL'
                        elif field == 'distributions':
                            flow_type = 'DIST'
                        elif field == 'fees':
                            flow_type = 'FEE'
                except (ValueError, TypeError):
                    continue
        
        if total_amount != 0 and flow_type and cashflow.get('flow_date'):
            return {
                'flow_type': flow_type,
                'amount': abs(total_amount),
                'flow_date': cashflow['flow_date'],
                'fund_id': doc_metadata.get('fund_id'),
                'investor_id': doc_metadata.get('investor_id'),
                'source_trace': {
                    'extraction_method': 'cas_excel_row',
                    'doc_type': 'CAS'
                }
            }
        
        return None
    
    def _extract_nav_from_row(self, row: List, col_mapping: Dict[str, int], doc_metadata: Dict) -> Optional[Dict[str, Any]]:
        """Extract NAV observation from a data row."""
        if 'ending_balance' not in col_mapping or 'date' not in col_mapping:
            return None
        
        try:
            nav_str = str(row[col_mapping['ending_balance']]).replace(',', '').replace('$', '').replace('€', '')
            nav_value = float(nav_str)
            as_of_date = self._parse_date(str(row[col_mapping['date']]))
            
            if nav_value and as_of_date:
                return {
                    'nav': nav_value,
                    'as_of_date': as_of_date,
                    'statement_date': as_of_date,
                    'scope': 'INVESTOR',
                    'investor_id': doc_metadata.get('investor_id'),
                    'scenario': 'AS_REPORTED',
                    'version_no': 1,
                    'source_trace': {
                        'extraction_method': 'cas_excel_nav',
                        'doc_type': 'CAS'
                    }
                }
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _extract_period_rollup(self, text: str) -> Dict[str, Any]:
        """Extract period rollup from CAS text."""
        rollup = {}
        
        # Common CAS patterns
        patterns = {
            'beginning_balance': r'beginning balance[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'contributions': r'contributions?[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'distributions': r'distributions?[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'fees': r'fees?[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'ending_balance': r'ending balance[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'unfunded': r'unfunded[:\s]+\$?([0-9,]+\.?[0-9]*)',
            'recallable': r'recallable[:\s]+\$?([0-9,]+\.?[0-9]*)'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1).replace(',', ''))
                    rollup[field] = value
                except ValueError:
                    continue
        
        # Extract dates
        date_patterns = [
            r'as of ([a-zA-Z]+ \d{1,2},? \d{4})',
            r'period ending ([a-zA-Z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parsed_date = self._parse_date(match.group(1))
                if parsed_date:
                    rollup['as_of_date'] = parsed_date
                    break
        
        return rollup
    
    def _extract_cashflows_from_table(self, table: Dict, doc_metadata: Dict) -> List[Dict[str, Any]]:
        """Extract individual cashflows from table."""
        cashflows = []
        headers = table.get('headers', [])
        rows = table.get('rows', [])
        
        # Find date and amount columns
        date_col = None
        amount_col = None
        type_col = None
        
        for idx, header in enumerate(headers):
            header_lower = str(header).lower()
            if 'date' in header_lower:
                date_col = idx
            elif any(term in header_lower for term in ['amount', 'value', 'total']):
                amount_col = idx
            elif any(term in header_lower for term in ['type', 'description', 'transaction']):
                type_col = idx
        
        for row in rows:
            if len(row) > max(date_col or 0, amount_col or 0):
                flow_date = None
                amount = None
                flow_type = 'OTHER'
                
                if date_col is not None and date_col < len(row):
                    flow_date = self._parse_date(str(row[date_col]))
                
                if amount_col is not None and amount_col < len(row):
                    try:
                        amount_str = str(row[amount_col]).replace(',', '').replace('$', '').replace('€', '')
                        amount = float(amount_str)
                    except (ValueError, TypeError):
                        continue
                
                if type_col is not None and type_col < len(row):
                    type_str = str(row[type_col]).lower()
                    if 'call' in type_str or 'contribution' in type_str:
                        flow_type = 'CALL'
                    elif 'distribution' in type_str or 'payout' in type_str:
                        flow_type = 'DIST'
                    elif 'fee' in type_str:
                        flow_type = 'FEE'
                
                if flow_date and amount and amount != 0:
                    cashflows.append({
                        'flow_type': flow_type,
                        'amount': abs(amount),
                        'flow_date': flow_date,
                        'fund_id': doc_metadata.get('fund_id'),
                        'investor_id': doc_metadata.get('investor_id'),
                        'source_trace': {
                            'extraction_method': 'cas_table_flow',
                            'table_idx': table.get('table_idx', 0),
                            'page_no': table.get('page_no', 1)
                        }
                    })
        
        return cashflows
    
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
cas_extractor = CASExtractor()