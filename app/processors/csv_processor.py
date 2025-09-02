"""CSV document processor."""

import pandas as pd
from typing import Dict, Any, List
from pathlib import Path
import json

from app.processors.base import DocumentProcessor
from app.processors.ai_classifier import AIClassifier


class CSVProcessor(DocumentProcessor):
    """CSV document processor."""
    
    supported_extensions = ['.csv']
    
    def __init__(self):
        super().__init__()
        self.ai_classifier = AIClassifier()
    
    def extract_text(self, file_path: str) -> str:
        """Extract text representation from CSV file."""
        try:
            # Read CSV with multiple encoding attempts
            encodings = ['utf-8', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise ValueError("Could not read CSV with any supported encoding")
            
            # Create text representation
            text_parts = []
            
            # Add header information
            text_parts.append(f"CSV File: {Path(file_path).name}")
            text_parts.append(f"Columns: {', '.join(df.columns.tolist())}")
            text_parts.append(f"Rows: {len(df)}")
            text_parts.append("")
            
            # Add sample data (first 10 rows)
            text_parts.append("Sample Data:")
            text_parts.append(df.head(10).to_string(index=False))
            
            # Add summary statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                text_parts.append("\nNumeric Summary:")
                text_parts.append(df[numeric_cols].describe().to_string())
            
            return "\n".join(text_parts)
            
        except Exception as e:
            raise ValueError(f"Error processing CSV file: {str(e)}")
    
    def extract_structured_data(self, text: str, file_path: str) -> Dict[str, Any]:
        """Extract structured data from CSV."""
        # Read the CSV again for structured processing
        try:
            encodings = ['utf-8', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise ValueError("Could not read CSV")
            
            # Use AI classifier for document type and summary
            classification_result = self.ai_classifier.classify_and_extract(
                text=text,
                filename=Path(file_path).name
            )
            
            # Extract CSV-specific structured data
            csv_data = self._extract_csv_data(df)
            
            # Merge results
            structured_data = {**classification_result, **csv_data}
            
            return structured_data
            
        except Exception as e:
            return {
                'document_type': 'other',
                'confidence_score': 0.0,
                'summary': f'Error processing CSV: {str(e)}',
                'error': str(e)
            }
    
    def _extract_csv_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract structured data from DataFrame."""
        data = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': df.columns.tolist(),
            'data_types': df.dtypes.astype(str).to_dict(),
        }
        
        # Detect potential financial data patterns
        financial_indicators = self._detect_financial_patterns(df)
        if financial_indicators:
            data['financial_indicators'] = financial_indicators
        
        # Extract date columns
        date_columns = self._detect_date_columns(df)
        if date_columns:
            data['date_columns'] = date_columns
            data['date_range'] = self._get_date_range(df, date_columns)
        
        # Sample data (first 5 rows)
        try:
            data['sample_data'] = df.head(5).to_dict('records')
        except Exception:
            data['sample_data'] = []
        
        # Summary statistics for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            data['numeric_columns'] = numeric_cols
            try:
                data['numeric_summary'] = df[numeric_cols].describe().to_dict()
            except Exception:
                pass
        
        return data
    
    def _detect_financial_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect financial data patterns in the DataFrame."""
        indicators = {}
        
        # Common financial column patterns
        financial_patterns = {
            'nav': ['nav', 'net_asset_value', 'net asset value'],
            'value': ['value', 'amount', 'total'],
            'performance': ['return', 'performance', 'yield', 'irr'],
            'dates': ['date', 'period', 'quarter', 'month', 'year'],
        }
        
        for category, patterns in financial_patterns.items():
            matching_columns = []
            for col in df.columns:
                col_lower = col.lower()
                if any(pattern in col_lower for pattern in patterns):
                    matching_columns.append(col)
            
            if matching_columns:
                indicators[category] = matching_columns
        
        return indicators
    
    def _detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect date columns in the DataFrame."""
        date_columns = []
        
        for col in df.columns:
            # Check if column name suggests it's a date
            col_lower = col.lower()
            if any(word in col_lower for word in ['date', 'time', 'period', 'quarter']):
                date_columns.append(col)
                continue
            
            # Try to parse a sample of values as dates
            try:
                sample = df[col].dropna().head(10)
                if len(sample) > 0:
                    pd.to_datetime(sample, errors='raise')
                    date_columns.append(col)
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