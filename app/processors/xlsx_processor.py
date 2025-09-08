"""Excel (XLSX) document processor."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.processors.ai_classifier import AIClassifier
from app.processors.base import DocumentProcessor


class XLSXProcessor(DocumentProcessor):
    """Excel document processor."""
    
    supported_extensions = ['.xlsx', '.xls']
    
    def __init__(self):
        super().__init__()
        self.ai_classifier = AIClassifier()
    
    def extract_text(self, file_path: str) -> str:
        """Extract text representation from Excel file."""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            text_parts = []
            
            text_parts.append(f"Excel File: {Path(file_path).name}")
            text_parts.append(f"Sheets: {', '.join(excel_file.sheet_names)}")
            text_parts.append("")
            
            # Process each sheet
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    text_parts.append(f"Sheet: {sheet_name}")
                    text_parts.append(f"Columns: {', '.join(df.columns.astype(str).tolist())}")
                    text_parts.append(f"Rows: {len(df)}")
                    
                    # Add sample data (first 5 rows)
                    if not df.empty:
                        text_parts.append("Sample Data:")
                        text_parts.append(df.head(5).to_string(index=False))
                    
                    text_parts.append("")
                    
                except Exception as e:
                    text_parts.append(f"Error reading sheet {sheet_name}: {str(e)}")
                    text_parts.append("")
            
            return "\n".join(text_parts)
            
        except Exception as e:
            raise ValueError(f"Error processing Excel file: {str(e)}")
    
    def extract_structured_data(self, text: str, file_path: str) -> Dict[str, Any]:
        """Extract structured data from Excel file."""
        try:
            # Use AI classifier for document type and summary
            classification_result = self.ai_classifier.classify_and_extract(
                text=text,
                filename=Path(file_path).name
            )
            
            # Extract Excel-specific structured data
            excel_data = self._extract_excel_data(file_path)
            
            # Merge results
            structured_data = {**classification_result, **excel_data}
            
            return structured_data
            
        except Exception as e:
            return {
                'document_type': 'other',
                'confidence_score': 0.0,
                'summary': f'Error processing Excel: {str(e)}',
                'error': str(e)
            }
    
    def _extract_excel_data(self, file_path: str) -> Dict[str, Any]:
        """Extract structured data from Excel file."""
        data = {}
        
        try:
            excel_file = pd.ExcelFile(file_path)
            data['sheet_names'] = excel_file.sheet_names
            data['sheet_count'] = len(excel_file.sheet_names)
            data['sheets'] = {}
            
            # Process each sheet
            for sheet_name in excel_file.sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    sheet_data = self._process_sheet(df, sheet_name)
                    data['sheets'][sheet_name] = sheet_data
                    
                except Exception as e:
                    data['sheets'][sheet_name] = {'error': str(e)}
            
            # Identify the main sheet (usually the largest or first)
            main_sheet = self._identify_main_sheet(data['sheets'])
            if main_sheet:
                data['main_sheet'] = main_sheet
                data.update(data['sheets'][main_sheet])
            
        except Exception as e:
            data['error'] = str(e)
        
        return data
    
    def _process_sheet(self, df: pd.DataFrame, sheet_name: str) -> Dict[str, Any]:
        """Process a single Excel sheet."""
        sheet_data = {
            'name': sheet_name,
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': df.columns.astype(str).tolist(),
        }
        
        if not df.empty:
            # Data types
            sheet_data['data_types'] = df.dtypes.astype(str).to_dict()
            
            # Detect financial patterns
            financial_indicators = self._detect_financial_patterns(df)
            if financial_indicators:
                sheet_data['financial_indicators'] = financial_indicators
            
            # Detect date columns
            date_columns = self._detect_date_columns(df)
            if date_columns:
                sheet_data['date_columns'] = date_columns
                sheet_data['date_range'] = self._get_date_range(df, date_columns)
            
            # Sample data (first 3 rows)
            try:
                sheet_data['sample_data'] = df.head(3).fillna('').to_dict('records')
            except Exception:
                pass
            
            # Summary statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if numeric_cols:
                sheet_data['numeric_columns'] = numeric_cols
                try:
                    sheet_data['numeric_summary'] = df[numeric_cols].describe().to_dict()
                except Exception:
                    pass
            
            # Check for pivot table or summary structure
            sheet_data['structure_type'] = self._identify_sheet_structure(df)
        
        return sheet_data
    
    def _identify_main_sheet(self, sheets_data: Dict[str, Any]) -> Optional[str]:
        """Identify the main sheet with the most relevant data."""
        if not sheets_data:
            return None
        
        # Score sheets based on various factors
        sheet_scores = {}
        
        for sheet_name, sheet_data in sheets_data.items():
            if 'error' in sheet_data:
                continue
                
            score = 0
            
            # Prefer sheets with more data
            score += sheet_data.get('row_count', 0) * 0.1
            score += sheet_data.get('column_count', 0) * 0.5
            
            # Prefer sheets with financial indicators
            if sheet_data.get('financial_indicators'):
                score += 50
            
            # Prefer sheets with date columns
            if sheet_data.get('date_columns'):
                score += 30
            
            # Prefer certain sheet names
            name_lower = sheet_name.lower()
            if any(keyword in name_lower for keyword in ['summary', 'data', 'main', 'report']):
                score += 20
            
            # Avoid sheets that look like metadata
            if any(keyword in name_lower for keyword in ['notes', 'info', 'metadata', 'config']):
                score -= 10
            
            sheet_scores[sheet_name] = score
        
        if sheet_scores:
            return max(sheet_scores, key=sheet_scores.get)
        
        return None
    
    def _detect_financial_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect financial data patterns in the DataFrame."""
        indicators = {}
        
        # Common financial column patterns
        financial_patterns = {
            'nav': ['nav', 'net_asset_value', 'net asset value', 'fund value'],
            'performance': ['return', 'performance', 'yield', 'irr', 'moic', 'tvpi', 'dpi'],
            'capital': ['capital', 'commitment', 'drawdown', 'distribution'],
            'valuation': ['value', 'valuation', 'fair value', 'market value'],
            'dates': ['date', 'period', 'quarter', 'month', 'year', 'as of'],
            'fund_info': ['fund', 'portfolio', 'investment', 'holding'],
        }
        
        for category, patterns in financial_patterns.items():
            matching_columns = []
            for col in df.columns:
                col_str = str(col).lower()
                if any(pattern in col_str for pattern in patterns):
                    matching_columns.append(str(col))
            
            if matching_columns:
                indicators[category] = matching_columns
        
        return indicators
    
    def _detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect date columns in the DataFrame."""
        date_columns = []
        
        for col in df.columns:
            col_str = str(col).lower()
            
            # Check if column name suggests it's a date
            if any(word in col_str for word in ['date', 'time', 'period', 'quarter', 'as of']):
                date_columns.append(str(col))
                continue
            
            # Try to parse a sample of values as dates
            try:
                sample = df[col].dropna().head(10)
                if len(sample) > 0:
                    pd.to_datetime(sample, errors='raise')
                    date_columns.append(str(col))
            except (ValueError, TypeError):
                pass
        
        return date_columns
    
    def _get_date_range(self, df: pd.DataFrame, date_columns: List[str]) -> Dict[str, Any]:
        """Get date range for detected date columns."""
        date_ranges = {}
        
        for col in date_columns:
            try:
                dates = pd.to_datetime(df[col], errors='coerce').dropna()
                if len(dates) > 0:
                    date_ranges[col] = {
                        'min_date': dates.min().isoformat(),
                        'max_date': dates.max().isoformat(),
                        'count': len(dates)
                    }
            except Exception:
                pass
        
        return date_ranges
    
    def _identify_sheet_structure(self, df: pd.DataFrame) -> str:
        """Identify the structure type of the sheet."""
        if df.empty:
            return 'empty'
        
        # Check for pivot table structure (multi-level columns/index)
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            return 'pivot_table'
        
        if hasattr(df.index, 'nlevels') and df.index.nlevels > 1:
            return 'pivot_table'
        
        # Check for time series (date column + numeric data)
        date_cols = self._detect_date_columns(df)
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if date_cols and numeric_cols:
            return 'time_series'
        
        # Check for summary/report structure (mostly text in first column, numbers in others)
        if len(df.columns) > 1:
            first_col_text_ratio = df.iloc[:, 0].astype(str).str.len().mean()
            other_cols_numeric = sum(1 for col in df.columns[1:] if pd.api.types.is_numeric_dtype(df[col]))
            
            if first_col_text_ratio > 10 and other_cols_numeric > 0:
                return 'summary_report'
        
        # Default to tabular data
        return 'tabular_data'