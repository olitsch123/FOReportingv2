"""Document processor factory."""

from typing import Optional, List
from pathlib import Path

from app.processors.base import DocumentProcessor
from app.processors.pdf_processor import PDFProcessor
from app.processors.csv_processor import CSVProcessor
from app.processors.xlsx_processor import XLSXProcessor


class ProcessorFactory:
    """Factory for creating document processors."""
    
    def __init__(self):
        """Initialize the factory with available processors."""
        self.processors = [
            PDFProcessor,
            CSVProcessor,
            XLSXProcessor,
        ]
    
    def get_processor(self, file_path: str) -> Optional[DocumentProcessor]:
        """Get the appropriate processor for a file."""
        for processor_class in self.processors:
            if processor_class.can_process(file_path):
                try:
                    return processor_class()
                except Exception as e:
                    print(f"Error initializing {processor_class.__name__}: {e}")
                    continue
        
        return None
    
    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions."""
        extensions = []
        for processor_class in self.processors:
            extensions.extend(processor_class.supported_extensions)
        return list(set(extensions))
    
    def can_process_file(self, file_path: str) -> bool:
        """Check if any processor can handle the file."""
        return any(
            processor_class.can_process(file_path)
            for processor_class in self.processors
        )