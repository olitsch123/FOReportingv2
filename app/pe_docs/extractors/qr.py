"""Quarterly Report extractor."""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re
from ..config import field_library

class QRExtractor:
    """Extract data from Quarterly Reports."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract NAV observations, performance metrics, and holdings from QR.
        """
        result = {
            'nav_observations': [],
            'performance_metrics': [],
            'holdings': [],
            'fees': []
        }
        
        text = parsed_data.get('text', '')
        tables = parsed_data.get('tables', [])
        
        # Extract NAV observations
        nav_obs = self._extract_nav_observations(text, tables, doc_metadata)
        result['nav_observations'].extend(nav_obs)
        
        # Extract performance metrics
        perf = self._extract_performance_metrics(text, tables)
        result['performance_metrics'].extend(perf)
        
        # Extract holdings if present
        holdings = self._extract_holdings(tables)
        result['holdings'].extend(holdings)
        
        # Extract fees
        fees = self._extract_fees(text, tables)
        result['fees'].extend(fees)
        
        return result
    
    def _extract_nav_observations(self, text: str, tables: List[Dict], doc_metadata: Dict) -> List[Dict[str, Any]]:
        """Extract NAV observations with as_of_date and statement_date."""
        observations = []
        
        # Look for NAV in text patterns
        nav_patterns = [
            r'net asset value[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'nav[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'ending balance[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        # Look for dates
        date_patterns = [
            r'as of ([a-zA-Z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        nav_value = None
        as_of_date = None
        
        # Extract NAV value
        for pattern in nav_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    nav_value = float(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
        
        # Extract date
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Parse different date formats
                    as_of_date = self._parse_date(date_str)
                    break
                except Exception:
                    continue
        
        # Extract from tables
        for table in tables:
            table_obs = self._extract_nav_from_table(table)
            observations.extend(table_obs)
        
        # Create observation if we found NAV and date
        if nav_value is not None and as_of_date:
            observation = {
                'nav': nav_value,
                'as_of_date': as_of_date,
                'statement_date': as_of_date,  # Same for QR typically
                'coverage_start': None,
                'coverage_end': as_of_date,
                'scope': 'FUND',  # QR is typically fund-level
                'investor_id': None,  # Fund-level
                'scenario': 'AS_REPORTED',
                'version_no': 1,
                'source_trace': {
                    'extraction_method': 'qr_text_pattern',
                    'doc_type': 'QR',
                    'confidence': 0.8
                }
            }
            observations.append(observation)
        
        return observations
    
    def _extract_nav_from_table(self, table: Dict) -> List[Dict[str, Any]]:
        """Extract NAV from table data."""
        observations = []
        headers = table.get('headers', [])
        rows = table.get('rows', [])
        
        if not headers or not rows:
            return observations
        
        # Find NAV and date columns
        nav_col = None
        date_col = None
        
        for idx, header in enumerate(headers):
            header_str = str(header).lower().strip()
            if any(term in header_str for term in ['nav', 'net asset', 'ending balance']):
                nav_col = idx
            elif any(term in header_str for term in ['date', 'as of', 'period']):
                date_col = idx
        
        # Extract observations from rows
        for row in rows:
            if len(row) > max(nav_col or 0, date_col or 0):
                nav_value = None
                as_of_date = None
                
                if nav_col is not None and nav_col < len(row):
                    try:
                        nav_str = str(row[nav_col]).replace(',', '').replace('$', '').replace('€', '')
                        nav_value = float(nav_str)
                    except (ValueError, TypeError):
                        continue
                
                if date_col is not None and date_col < len(row):
                    as_of_date = self._parse_date(str(row[date_col]))
                
                if nav_value is not None and as_of_date:
                    observation = {
                        'nav': nav_value,
                        'as_of_date': as_of_date,
                        'statement_date': as_of_date,
                        'scope': 'FUND',
                        'investor_id': None,
                        'scenario': 'AS_REPORTED',
                        'version_no': 1,
                        'source_trace': {
                            'extraction_method': 'qr_table',
                            'table_idx': table.get('table_idx', 0),
                            'page_no': table.get('page_no', 1)
                        }
                    }
                    observations.append(observation)
        
        return observations
    
    def _extract_performance_metrics(self, text: str, tables: List[Dict]) -> List[Dict[str, Any]]:
        """Extract performance metrics like IRR, MOIC, DPI, etc."""
        metrics = []
        
        # Performance patterns
        patterns = {
            'irr': r'irr[:\s]+([0-9]+\.?[0-9]*)\s*%?',
            'moic': r'moic[:\s]+([0-9]+\.?[0-9]*)',
            'dpi': r'dpi[:\s]+([0-9]+\.?[0-9]*)',
            'rvpi': r'rvpi[:\s]+([0-9]+\.?[0-9]*)',
            'tvpi': r'tvpi[:\s]+([0-9]+\.?[0-9]*)'
        }
        
        extracted_metrics = {}
        for metric, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    if metric == 'irr':
                        value = value / 100  # Convert percentage to decimal
                    extracted_metrics[metric] = value
                except ValueError:
                    continue
        
        if extracted_metrics:
            metrics.append({
                'metrics': extracted_metrics,
                'source_trace': {
                    'extraction_method': 'qr_performance_text',
                    'doc_type': 'QR'
                }
            })
        
        return metrics
    
    def _extract_holdings(self, tables: List[Dict]) -> List[Dict[str, Any]]:
        """Extract holdings/portfolio information."""
        holdings = []
        
        for table in tables:
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            
            # Look for holdings table patterns
            header_str = ' '.join(str(h).lower() for h in headers)
            if any(term in header_str for term in ['company', 'investment', 'holding', 'portfolio']):
                
                # Find relevant columns
                company_col = None
                value_col = None
                
                for idx, header in enumerate(headers):
                    header_lower = str(header).lower()
                    if any(term in header_lower for term in ['company', 'investment', 'name']):
                        company_col = idx
                    elif any(term in header_lower for term in ['value', 'fair value', 'market value']):
                        value_col = idx
                
                # Extract holdings
                for row in rows:
                    if len(row) > max(company_col or 0, value_col or 0):
                        holding = {}
                        
                        if company_col is not None and company_col < len(row):
                            holding['company_name'] = str(row[company_col]).strip()
                        
                        if value_col is not None and value_col < len(row):
                            try:
                                value_str = str(row[value_col]).replace(',', '').replace('$', '').replace('€', '')
                                holding['fair_value'] = float(value_str)
                            except (ValueError, TypeError):
                                continue
                        
                        if holding.get('company_name') and holding.get('fair_value'):
                            holding['source_trace'] = {
                                'extraction_method': 'qr_holdings_table',
                                'table_idx': table.get('table_idx', 0),
                                'page_no': table.get('page_no', 1)
                            }
                            holdings.append(holding)
        
        return holdings
    
    def _extract_fees(self, text: str, tables: List[Dict]) -> List[Dict[str, Any]]:
        """Extract fee information."""
        fees = []
        
        # Fee patterns in text
        fee_patterns = [
            r'management fee[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'admin fee[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'performance fee[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in fee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    fee_amount = float(match.group(1).replace(',', ''))
                    fee_type = pattern.split('[')[0].replace('\\\\', '').strip()
                    
                    fees.append({
                        'fee_type': fee_type,
                        'amount': fee_amount,
                        'source_trace': {
                            'extraction_method': 'qr_fee_text',
                            'pattern': pattern
                        }
                    })
                except ValueError:
                    continue
        
        return fees
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        if not date_str or str(date_str).strip() in ['', 'nan', 'None']:
            return None
        
        date_str = str(date_str).strip()
        
        # Common date formats
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
qr_extractor = QRExtractor()