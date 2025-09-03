"""Excel parsing for PE documents."""
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
from ..config import field_library

class ExcelParser:
    """Excel parser for PE fund documents."""
    
    def __init__(self):
        self.tab_mappings = {
            'cashflows': ['cashflow', 'cash flow', 'flows', 'transactions'],
            'capital_account': ['capital account', 'capital', 'account', 'cas'],
            'fees': ['fees', 'fee', 'management fee', 'expenses'],
            'nav': ['nav', 'net asset value', 'valuation', 'balance'],
            'holdings': ['holdings', 'portfolio', 'investments', 'positions']
        }
    
    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Excel document extracting structured data from tabs.
        Returns structured data for PE document processing.
        """
        file_path = Path(file_path)
        
        result = {
            'tabs': {},
            'structured_data': {},
            'metadata': {
                'filename': file_path.name,
                'tab_count': 0
            }
        }
        
        try:
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None, header=None)
            result['metadata']['tab_count'] = len(excel_data)
            
            for sheet_name, df in excel_data.items():
                tab_data = self._process_tab(sheet_name, df)
                result['tabs'][sheet_name] = tab_data
                
                # Map to structured categories
                category = self._categorize_tab(sheet_name)
                if category:
                    if category not in result['structured_data']:
                        result['structured_data'][category] = []
                    result['structured_data'][category].append(tab_data)
        
        except Exception as e:
            result['error'] = f"Excel parsing failed: {str(e)}"
        
        return result
    
    def _process_tab(self, sheet_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Process individual Excel tab."""
        tab_data = {
            'name': sheet_name,
            'headers': [],
            'data': [],
            'mapped_columns': {},
            'row_count': len(df),
            'col_count': len(df.columns)
        }
        
        if df.empty:
            return tab_data
        
        # Find header row (look for row with most non-null values)
        header_row_idx = 0
        max_non_null = 0
        
        for idx in range(min(10, len(df))):  # Check first 10 rows
            non_null_count = df.iloc[idx].notna().sum()
            if non_null_count > max_non_null:
                max_non_null = non_null_count
                header_row_idx = idx
        
        # Extract headers
        if header_row_idx < len(df):
            headers = df.iloc[header_row_idx].fillna('').astype(str).tolist()
            tab_data['headers'] = headers
            
            # Map headers to canonical fields
            for col_idx, header in enumerate(headers):
                if header.strip():
                    canonical = field_library.get_canonical_field(header.strip())
                    if canonical:
                        tab_data['mapped_columns'][col_idx] = canonical
        
        # Extract data rows (skip header and empty rows)
        data_start = header_row_idx + 1
        if data_start < len(df):
            for row_idx in range(data_start, len(df)):
                row = df.iloc[row_idx].fillna('').tolist()
                # Skip completely empty rows
                if any(str(cell).strip() for cell in row):
                    tab_data['data'].append(row)
        
        return tab_data
    
    def _categorize_tab(self, sheet_name: str) -> Optional[str]:
        """Categorize tab based on name."""
        sheet_lower = sheet_name.lower()
        
        for category, keywords in self.tab_mappings.items():
            for keyword in keywords:
                if keyword in sheet_lower:
                    return category
        
        return None
    
    def extract_nav_data(self, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract NAV observations from structured Excel data."""
        nav_observations = []
        
        # Look for NAV data in relevant tabs
        nav_tabs = structured_data.get('nav', []) + structured_data.get('capital_account', [])
        
        for tab in nav_tabs:
            mapped_cols = tab.get('mapped_columns', {})
            headers = tab.get('headers', [])
            data_rows = tab.get('data', [])
            
            # Find columns for NAV extraction
            nav_col = None
            date_col = None
            
            for col_idx, canonical in mapped_cols.items():
                if 'nav' in canonical.lower() or 'ending_balance' in canonical.lower():
                    nav_col = col_idx
                elif 'date' in canonical.lower() or 'report_date' in canonical.lower():
                    date_col = col_idx
            
            # Extract NAV observations
            for row in data_rows:
                if len(row) > max(nav_col or 0, date_col or 0):
                    observation = {}
                    
                    if nav_col is not None and nav_col < len(row):
                        try:
                            nav_value = float(str(row[nav_col]).replace(',', '').replace('$', '').replace('€', ''))
                            observation['nav'] = nav_value
                        except (ValueError, TypeError):
                            continue
                    
                    if date_col is not None and date_col < len(row):
                        observation['as_of_date'] = str(row[date_col])
                    
                    if observation:
                        observation['source_tab'] = tab['name']
                        nav_observations.append(observation)
        
        return nav_observations

# Global parser instance
excel_parser = ExcelParser()