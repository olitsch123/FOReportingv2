"""Document tracking with hash-based identification."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
Base = declarative_base()


class DocumentTracker(Base):
    """Track all documents with hash-based identification."""
    __tablename__ = 'document_tracker'
    
    id = Column(Integer, primary_key=True)
    file_path = Column(String(1000), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 hash
    file_size = Column(Integer)
    
    # Processing status
    status = Column(String(50), default='discovered')  # discovered, processing, completed, failed
    error_message = Column(Text)
    
    # Timestamps
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_modified = Column(DateTime)
    last_processed = Column(DateTime)
    processing_count = Column(Integer, default=0)
    
    # Extracted metadata
    document_type = Column(String(100))
    fund_name = Column(String(200))
    investor_name = Column(String(200))
    period_date = Column(DateTime)
    
    # Storage references
    document_id = Column(Integer)  # Reference to documents table
    pe_document_id = Column(Integer)  # Reference to pe_document table
    extracted_records = Column(Integer, default=0)  # Number of records extracted
    
    __table_args__ = (
        UniqueConstraint('file_path', 'file_hash', name='uq_path_hash'),
    )


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}")
        return ""


class DocumentTrackerService:
    """Service for tracking documents."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def track_document(self, file_path: str) -> Optional[DocumentTracker]:
        """Track a document, creating or updating its record."""
        try:
            # Calculate hash
            file_hash = calculate_file_hash(file_path)
            if not file_hash:
                return None
            
            # Get file info
            path = Path(file_path)
            file_size = path.stat().st_size
            last_modified = datetime.fromtimestamp(path.stat().st_mtime)
            
            # Check if already exists
            existing = self.db.query(DocumentTracker).filter_by(
                file_hash=file_hash
            ).first()
            
            if existing:
                # Update existing record
                existing.file_path = str(file_path)  # Path might have changed
                existing.last_modified = last_modified
                existing.file_size = file_size
                
                # Check if file changed (shouldn't happen with same hash, but check anyway)
                if existing.last_modified < last_modified:
                    existing.status = 'discovered'  # Mark for reprocessing
                
                self.db.commit()
                return existing
            else:
                # Create new record
                tracker = DocumentTracker(
                    file_path=str(file_path),
                    file_name=path.name,
                    file_hash=file_hash,
                    file_size=file_size,
                    last_modified=last_modified,
                    status='discovered'
                )
                self.db.add(tracker)
                self.db.commit()
                return tracker
                
        except Exception as e:
            logger.error(f"Error tracking document {file_path}: {e}")
            self.db.rollback()
            return None
    
    def mark_processing(self, file_hash: str) -> bool:
        """Mark document as processing."""
        try:
            tracker = self.db.query(DocumentTracker).filter_by(
                file_hash=file_hash
            ).first()
            
            if tracker:
                tracker.status = 'processing'
                tracker.processing_count += 1
                self.db.commit()
                return True
            return False
        except Exception:
            self.db.rollback()
            return False
    
    def mark_completed(self, file_hash: str, document_id: int = None, 
                      pe_document_id: int = None, metadata: dict = None) -> bool:
        """Mark document as completed."""
        try:
            tracker = self.db.query(DocumentTracker).filter_by(
                file_hash=file_hash
            ).first()
            
            if tracker:
                tracker.status = 'completed'
                tracker.last_processed = datetime.utcnow()
                tracker.error_message = None
                
                if document_id:
                    tracker.document_id = document_id
                if pe_document_id:
                    tracker.pe_document_id = pe_document_id
                    
                # Update metadata if provided
                if metadata:
                    tracker.document_type = metadata.get('document_type')
                    tracker.fund_name = metadata.get('fund_name')
                    tracker.investor_name = metadata.get('investor_name')
                    if metadata.get('period_date'):
                        tracker.period_date = metadata['period_date']
                
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking completed: {e}")
            self.db.rollback()
            return False
    
    def mark_failed(self, file_hash: str, error_message: str) -> bool:
        """Mark document as failed."""
        try:
            tracker = self.db.query(DocumentTracker).filter_by(
                file_hash=file_hash
            ).first()
            
            if tracker:
                tracker.status = 'failed'
                tracker.error_message = error_message
                tracker.last_processed = datetime.utcnow()
                self.db.commit()
                return True
            return False
        except Exception:
            self.db.rollback()
            return False
    
    def is_new_or_modified(self, file_path: str) -> bool:
        """Check if document is new or modified since last processing."""
        file_hash = calculate_file_hash(file_path)
        if not file_hash:
            return True  # Assume new if can't hash
        
        tracker = self.db.query(DocumentTracker).filter_by(
            file_hash=file_hash
        ).first()
        
        if not tracker:
            return True  # New file
        
        # Check if needs reprocessing
        return tracker.status in ['discovered', 'failed']
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        stats = {
            'total': self.db.query(DocumentTracker).count(),
            'discovered': self.db.query(DocumentTracker).filter_by(status='discovered').count(),
            'processing': self.db.query(DocumentTracker).filter_by(status='processing').count(),
            'completed': self.db.query(DocumentTracker).filter_by(status='completed').count(),
            'failed': self.db.query(DocumentTracker).filter_by(status='failed').count()
        }
        return stats
    
    def get_documents_for_export(self, status: str = None) -> List[Dict]:
        """Get documents for CSV export."""
        query = self.db.query(DocumentTracker)
        
        if status:
            query = query.filter_by(status=status)
        
        documents = []
        for doc in query.all():
            documents.append({
                'id': doc.id,
                'file_name': doc.file_name,
                'file_path': doc.file_path,
                'file_hash': doc.file_hash,
                'file_size': doc.file_size,
                'status': doc.status,
                'error_message': doc.error_message,
                'first_seen': doc.first_seen.isoformat() if doc.first_seen else None,
                'last_modified': doc.last_modified.isoformat() if doc.last_modified else None,
                'last_processed': doc.last_processed.isoformat() if doc.last_processed else None,
                'processing_count': doc.processing_count,
                'document_type': doc.document_type,
                'fund_name': doc.fund_name,
                'investor_name': doc.investor_name,
                'period_date': doc.period_date.isoformat() if doc.period_date else None,
                'document_id': doc.document_id,
                'pe_document_id': doc.pe_document_id,
                'extracted_records': doc.extracted_records
            })
        
        return documents