"""PDF document processor."""

import re
from typing import Dict, Any, List
from pathlib import Path

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from app.processors.base import DocumentProcessor
from app.processors.ai_classifier import AIClassifier


class PDFProcessor(DocumentProcessor):
    """PDF document processor."""
    
    supported_extensions = ['.pdf']
    
    def __init__(self):
        super().__init__()
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is required for PDF processing")
        self.ai_classifier = AIClassifier()
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
                    
        except Exception as e:
            raise ValueError(f"Error extracting text from PDF: {str(e)}")
        
        return text.strip()
    
    def extract_structured_data(self, text: str, file_path: str) -> Dict[str, Any]:
        """Extract structured data from PDF text using AI."""
        # Use AI classifier to determine document type and extract data
        classification_result = self.ai_classifier.classify_and_extract(
            text=text,
            filename=Path(file_path).name
        )
        
        # Extract additional metadata specific to PDFs
        additional_data = self._extract_pdf_metadata(text)
        
        # Merge AI results with PDF-specific metadata
        structured_data = {**classification_result, **additional_data}
        
        return structured_data
    
    def _extract_pdf_metadata(self, text: str) -> Dict[str, Any]:
        """Extract PDF-specific metadata using regex patterns."""
        metadata = {}
        
        # Common patterns for financial documents
        patterns = {
            'nav_values': r'NAV[:\s]*([€$£]?[\d,]+\.?\d*)',
            'dates': r'(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}-\d{2}-\d{2})',
            'percentages': r'(\d+\.?\d*%)',
            'amounts': r'([€$£]\s?[\d,]+\.?\d*[KMB]?)',
            'fund_names': r'Fund[:\s]*([A-Z][A-Za-z\s&]+)',
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                metadata[key] = matches[:10]  # Limit to first 10 matches
        
        return metadata