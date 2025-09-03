"""Core PDF parsing functionality for PE documents."""
import io
import re
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import PyPDF2
import pdfplumber
import pytesseract
from PIL import Image

class PDFParser:
    """Core PDF parsing with text and table extraction."""
    
    def __init__(self):
        self.text_extractors = ['pdfplumber', 'pypdf2']
        self.table_extractors = ['pdfplumber', 'camelot']
    
    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF document extracting text, tables, and metadata.
        Returns structured data for PE document processing.
        """
        file_path = Path(file_path)
        
        result = {
            'pages': [],
            'text': '',
            'tables': [],
            'metadata': {},
            'page_count': 0
        }
        
        try:
            # Extract with pdfplumber (primary)
            with pdfplumber.open(file_path) as pdf:
                result['page_count'] = len(pdf.pages)
                result['metadata'] = self._extract_metadata(pdf)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    page_data = {
                        'page_no': page_num,
                        'text': '',
                        'tables': [],
                        'bbox': None
                    }
                    
                    # Extract text
                    page_text = page.extract_text() or ''
                    page_data['text'] = page_text
                    result['text'] += f"\\n--- Page {page_num} ---\\n{page_text}"
                    
                    # Extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table_idx, table in enumerate(tables):
                            if table and len(table) > 0:
                                table_data = {
                                    'page_no': page_num,
                                    'table_idx': table_idx,
                                    'headers': table[0] if table else [],
                                    'rows': table[1:] if len(table) > 1 else [],
                                    'bbox': None  # Could extract bbox if needed
                                }
                                page_data['tables'].append(table_data)
                                result['tables'].append(table_data)
                    
                    result['pages'].append(page_data)
        
        except Exception as e:
            # Fallback to PyPDF2
            try:
                result = self._fallback_pypdf2(file_path)
            except Exception as fallback_e:
                result['error'] = f"PDF parsing failed: {str(e)}, fallback: {str(fallback_e)}"
        
        return result
    
    def _extract_metadata(self, pdf) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = {}
        try:
            if hasattr(pdf, 'metadata') and pdf.metadata:
                for key, value in pdf.metadata.items():
                    if isinstance(value, str):
                        metadata[key.replace('/', '')] = value
        except Exception:
            pass
        return metadata
    
    def _fallback_pypdf2(self, file_path: Path) -> Dict[str, Any]:
        """Fallback parser using PyPDF2."""
        result = {
            'pages': [],
            'text': '',
            'tables': [],
            'metadata': {},
            'page_count': 0
        }
        
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            result['page_count'] = len(reader.pages)
            
            # Extract metadata
            if reader.metadata:
                for key, value in reader.metadata.items():
                    if isinstance(value, str):
                        result['metadata'][key.replace('/', '')] = value
            
            # Extract text from each page
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    page_text = page.extract_text() or ''
                    page_data = {
                        'page_no': page_num,
                        'text': page_text,
                        'tables': [],
                        'bbox': None
                    }
                    result['pages'].append(page_data)
                    result['text'] += f"\\n--- Page {page_num} ---\\n{page_text}"
                except Exception:
                    continue
        
        return result
    
    def extract_key_phrases(self, text: str, doc_type: str) -> List[str]:
        """Extract key phrases relevant to document type."""
        phrases = []
        
        # Get anchors for document type
        anchors = field_library.get_anchors_for_doc_type(doc_type)
        
        for anchor in anchors:
            try:
                matches = re.findall(anchor, text, re.IGNORECASE)
                phrases.extend(matches)
            except re.error:
                continue
        
        return list(set(phrases))  # Remove duplicates

# Global parser instance
pdf_parser = PDFParser()