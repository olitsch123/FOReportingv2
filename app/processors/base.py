"""Base document processor interface."""

import hashlib
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.database.models import DocumentType


@dataclass
class ProcessedDocument:
    """Processed document data structure."""
    filename: str
    file_path: str
    file_size: int
    file_hash: str
    mime_type: str
    raw_text: str
    document_type: DocumentType
    confidence_score: float
    structured_data: Dict[str, Any]
    summary: str
    reporting_date: Optional[str] = None


class DocumentProcessor(ABC):
    """Base class for document processors."""
    
    supported_extensions: List[str] = []
    
    def __init__(self):
        """Initialize the processor."""
        pass
    
    @classmethod
    def can_process(cls, file_path: str) -> bool:
        """Check if this processor can handle the given file."""
        return Path(file_path).suffix.lower() in cls.supported_extensions
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract basic file metadata."""
        path = Path(file_path)
        
        # Calculate file hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            'filename': path.name,
            'file_path': str(path.absolute()),
            'file_size': path.stat().st_size,
            'file_hash': file_hash,
            'mime_type': mime_type or 'application/octet-stream',
        }
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extract raw text from the document."""
        pass
    
    @abstractmethod
    def extract_structured_data(self, text: str, file_path: str) -> Dict[str, Any]:
        """Extract structured data from the document text."""
        pass
    
    def process(self, file_path: str) -> ProcessedDocument:
        """Process a document and return structured data."""
        # Get basic metadata
        metadata = self.get_file_metadata(file_path)
        
        # Extract text
        raw_text = self.extract_text(file_path)
        
        # Extract structured data
        structured_data = self.extract_structured_data(raw_text, file_path)
        
        # Create processed document
        return ProcessedDocument(
            filename=metadata['filename'],
            file_path=metadata['file_path'],
            file_size=metadata['file_size'],
            file_hash=metadata['file_hash'],
            mime_type=metadata['mime_type'],
            raw_text=raw_text,
            document_type=structured_data.get('document_type', DocumentType.OTHER),
            confidence_score=structured_data.get('confidence_score', 0.0),
            structured_data=structured_data,
            summary=structured_data.get('summary', ''),
            reporting_date=structured_data.get('reporting_date'),
        )