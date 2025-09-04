"""Core PDF parsing functionality for PE documents."""

import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import PyPDF2
import pdfplumber
import pytesseract
from PIL import Image
import io
from structlog import get_logger
from app.pe_docs.config import get_pe_config

logger = get_logger()
pe_config = get_pe_config()


class PDFParser:
    """Parse PE PDF documents with text and table extraction."""
    
    def __init__(self):
        """Initialize PDF parser."""
        self.ocr_threshold = 100  # Min chars per page before OCR
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract text, tables, and metadata.
        
        Returns:
            Dict with:
            - text: Full text content
            - pages: List of page data with text and tables
            - metadata: PDF metadata
            - ocr_used: Whether OCR was used
        """
        result = {
            'text': '',
            'pages': [],
            'metadata': {},
            'ocr_used': False
        }
        
        try:
            # Try pdfplumber first (better table extraction)
            result_plumber = self._parse_with_pdfplumber(file_path)
            if result_plumber['text'] and len(result_plumber['text']) > self.ocr_threshold:
                logger.info(
                    "pdf_parsed_with_pdfplumber",
                    file_path=file_path,
                    pages=len(result_plumber['pages']),
                    text_length=len(result_plumber['text'])
                )
                return result_plumber
        except Exception as e:
            logger.warning(
                "pdfplumber_failed",
                file_path=file_path,
                error=str(e)
            )
        
        try:
            # Fallback to PyPDF2
            result_pypdf = self._parse_with_pypdf2(file_path)
            if result_pypdf['text'] and len(result_pypdf['text']) > self.ocr_threshold:
                logger.info(
                    "pdf_parsed_with_pypdf2",
                    file_path=file_path,
                    pages=len(result_pypdf['pages']),
                    text_length=len(result_pypdf['text'])
                )
                return result_pypdf
        except Exception as e:
            logger.warning(
                "pypdf2_failed",
                file_path=file_path,
                error=str(e)
            )
        
        # Last resort: OCR
        try:
            result_ocr = self._parse_with_ocr(file_path)
            result_ocr['ocr_used'] = True
            logger.info(
                "pdf_parsed_with_ocr",
                file_path=file_path,
                pages=len(result_ocr['pages']),
                text_length=len(result_ocr['text'])
            )
            return result_ocr
        except Exception as e:
            logger.error(
                "pdf_parse_failed",
                file_path=file_path,
                error=str(e)
            )
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    
    def _parse_with_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF using pdfplumber."""
        result = {
            'text': '',
            'pages': [],
            'metadata': {}
        }
        
        with pdfplumber.open(file_path) as pdf:
            # Extract metadata
            if pdf.metadata:
                result['metadata'] = {
                    'title': pdf.metadata.get('Title', ''),
                    'author': pdf.metadata.get('Author', ''),
                    'subject': pdf.metadata.get('Subject', ''),
                    'creator': pdf.metadata.get('Creator', ''),
                    'producer': pdf.metadata.get('Producer', ''),
                    'creation_date': str(pdf.metadata.get('CreationDate', '')),
                    'modification_date': str(pdf.metadata.get('ModDate', '')),
                }
            
            # Extract pages
            for page_num, page in enumerate(pdf.pages):
                page_data = {
                    'page_num': page_num + 1,
                    'text': '',
                    'tables': [],
                    'bbox': {}
                }
                
                # Extract text
                text = page.extract_text() or ''
                page_data['text'] = text
                result['text'] += text + '\n'
                
                # Extract tables
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    # Clean table data
                    cleaned_table = []
                    for row in table:
                        cleaned_row = [cell.strip() if cell else '' for cell in row]
                        if any(cleaned_row):  # Skip empty rows
                            cleaned_table.append(cleaned_row)
                    
                    if cleaned_table:
                        page_data['tables'].append({
                            'index': table_idx,
                            'data': cleaned_table,
                            'rows': len(cleaned_table),
                            'cols': len(cleaned_table[0]) if cleaned_table else 0
                        })
                
                # Extract bounding boxes for key elements
                if page.chars:
                    page_data['bbox'] = {
                        'width': page.width,
                        'height': page.height
                    }
                
                result['pages'].append(page_data)
        
        return result
    
    def _parse_with_pypdf2(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF using PyPDF2."""
        result = {
            'text': '',
            'pages': [],
            'metadata': {}
        }
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Extract metadata
            if pdf_reader.metadata:
                result['metadata'] = {
                    'title': pdf_reader.metadata.get('/Title', ''),
                    'author': pdf_reader.metadata.get('/Author', ''),
                    'subject': pdf_reader.metadata.get('/Subject', ''),
                    'creator': pdf_reader.metadata.get('/Creator', ''),
                    'producer': pdf_reader.metadata.get('/Producer', ''),
                }
            
            # Extract pages
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                page_data = {
                    'page_num': page_num + 1,
                    'text': text,
                    'tables': []  # PyPDF2 doesn't extract tables
                }
                
                result['pages'].append(page_data)
                result['text'] += text + '\n'
        
        return result
    
    def _parse_with_ocr(self, file_path: str) -> Dict[str, Any]:
        """Parse PDF using OCR."""
        result = {
            'text': '',
            'pages': [],
            'metadata': {'ocr_used': True}
        }
        
        # Convert PDF to images and OCR each page
        try:
            import pdf2image
            images = pdf2image.convert_from_path(file_path)
            
            for page_num, image in enumerate(images):
                # OCR the image
                text = pytesseract.image_to_string(image)
                
                page_data = {
                    'page_num': page_num + 1,
                    'text': text,
                    'tables': []
                }
                
                result['pages'].append(page_data)
                result['text'] += text + '\n'
                
        except ImportError:
            # If pdf2image not available, try with PyPDF2 + PIL
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    
                    # Try to extract images from page
                    if '/XObject' in page['/Resources']:
                        xobject = page['/Resources']['/XObject'].get_object()
                        
                        for obj in xobject:
                            if xobject[obj]['/Subtype'] == '/Image':
                                # Extract and OCR image
                                # This is simplified - real implementation would need more work
                                pass
        
        return result
    
    def extract_structured_tables(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and structure tables from parsed pages."""
        structured_tables = []
        
        for page in pages:
            for table in page.get('tables', []):
                # Analyze table structure
                table_data = table.get('data', [])
                if not table_data:
                    continue
                
                # Try to identify headers
                headers = self._identify_headers(table_data)
                
                # Convert to structured format
                if headers:
                    structured = self._table_to_dict(table_data, headers)
                    structured_tables.append({
                        'page': page['page_num'],
                        'headers': headers,
                        'data': structured,
                        'raw': table_data
                    })
        
        return structured_tables
    
    def _identify_headers(self, table_data: List[List[str]]) -> Optional[List[str]]:
        """Identify table headers."""
        if not table_data:
            return None
        
        # Check first row
        first_row = table_data[0]
        
        # Heuristics for header detection
        if all(cell and not cell[0].isdigit() for cell in first_row):
            # Map headers to canonical fields
            headers = []
            for cell in first_row:
                canonical = pe_config.get_column_mapping(cell)
                headers.append(canonical or cell)
            return headers
        
        return None
    
    def _table_to_dict(self, table_data: List[List[str]], headers: List[str]) -> List[Dict[str, Any]]:
        """Convert table to list of dictionaries."""
        result = []
        
        for row_idx, row in enumerate(table_data[1:]):  # Skip header row
            row_dict = {}
            for col_idx, cell in enumerate(row):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    # Clean and parse cell value
                    value = self._parse_cell_value(cell, header)
                    row_dict[header] = value
            
            if any(row_dict.values()):  # Skip empty rows
                result.append(row_dict)
        
        return result
    
    def _parse_cell_value(self, cell: str, header: str) -> Any:
        """Parse cell value based on header type."""
        if not cell:
            return None
        
        cell = cell.strip()
        
        # Check if numeric
        if header in ['nav', 'commitment', 'distributions', 'contributions']:
            # Remove currency symbols and parse
            cell_clean = re.sub(r'[$€£,()]', '', cell)
            cell_clean = cell_clean.replace('(', '-').replace(')', '')
            
            try:
                # Check for multipliers
                if 'k' in cell_clean.lower():
                    return float(cell_clean.lower().replace('k', '')) * 1000
                elif 'm' in cell_clean.lower():
                    return float(cell_clean.lower().replace('m', '')) * 1000000
                else:
                    return float(cell_clean)
            except ValueError:
                return cell
        
        # Check if percentage
        if header in ['irr', 'moic', 'dpi', 'rvpi', 'tvpi'] and '%' in cell:
            try:
                return float(cell.replace('%', '')) / 100
            except ValueError:
                return cell
        
        return cell