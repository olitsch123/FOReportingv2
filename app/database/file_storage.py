"""File-based storage for development/fallback mode."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FileStorageService:
    """File-based storage service for when database is unavailable."""
    
    def __init__(self, storage_dir: str = "./data/storage"):
        """Initialize file storage."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage files
        self.investors_file = self.storage_dir / "investors.json"
        self.documents_file = self.storage_dir / "documents.json"
        self.funds_file = self.storage_dir / "funds.json"
        
        # Initialize storage files
        self._init_storage_files()
        
    def _init_storage_files(self):
        """Initialize storage files with default data."""
        # Initialize investors
        if not self.investors_file.exists():
            default_investors = [
                {
                    "id": "brainweb-001",
                    "name": "BrainWeb Investment GmbH",
                    "code": "brainweb",
                    "description": "BrainWeb Investment GmbH - Private Equity and Venture Capital",
                    "folder_path": "",
                    "created_at": datetime.now().isoformat(),
                    "status": "active"
                },
                {
                    "id": "pecunalta-001",
                    "name": "pecunalta GmbH", 
                    "code": "pecunalta",
                    "description": "pecunalta GmbH - Investment Management",
                    "folder_path": "",
                    "created_at": datetime.now().isoformat(),
                    "status": "active"
                }
            ]
            self._save_json(self.investors_file, default_investors)
        
        # Initialize empty documents and funds
        if not self.documents_file.exists():
            self._save_json(self.documents_file, [])
        
        if not self.funds_file.exists():
            self._save_json(self.funds_file, [])
    
    def _load_json(self, file_path: Path) -> List[Dict]:
        """Load JSON data from file."""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
        return []
    
    def _save_json(self, file_path: Path, data: List[Dict]):
        """Save JSON data to file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")
    
    def get_investors(self) -> List[Dict]:
        """Get all investors."""
        return self._load_json(self.investors_file)
    
    def get_documents(self, investor_code: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get documents with optional filtering."""
        documents = self._load_json(self.documents_file)
        
        if investor_code:
            documents = [doc for doc in documents if doc.get("investor_code") == investor_code]
        
        return documents[:limit]
    
    def save_document(self, document_data: Dict) -> str:
        """Save a document."""
        documents = self._load_json(self.documents_file)
        
        # Add metadata
        document_data["id"] = str(uuid.uuid4())
        document_data["created_at"] = datetime.now().isoformat()
        document_data["processing_status"] = "completed"
        
        documents.append(document_data)
        self._save_json(self.documents_file, documents)
        
        logger.info(f"Saved document: {document_data.get('filename', 'unknown')}")
        return document_data["id"]
    
    def get_stats(self) -> Dict:
        """Get storage statistics."""
        investors = self.get_investors()
        documents = self.get_documents()
        
        return {
            "total_investors": len(investors),
            "total_documents": len(documents),
            "storage_mode": "file_based",
            "status": "operational"
        }