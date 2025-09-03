"""File ledger for idempotent processing."""
import hashlib
from typing import Dict, List, Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text

class FileLedger:
    """SHA-256 file ledger for idempotent processing."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def is_file_processed(self, file_path: str) -> bool:
        """Check if file has been processed (by hash)."""
        file_hash = self.calculate_file_hash(file_path)
        
        result = self.db.execute(
            text("SELECT 1 FROM ingestion_file WHERE file_hash = :file_hash"),
            {'file_hash': file_hash}
        ).fetchone()
        
        return result is not None
    
    def register_file(self, file_path: str, org_code: str, investor_code: str, 
                     source_system: str = 'windows_watch') -> int:
        """
        Register file in ledger.
        Returns file_id.
        """
        file_path = Path(file_path)
        file_hash = self.calculate_file_hash(str(file_path))
        
        # Check if already exists
        existing = self.db.execute(
            text("SELECT file_id FROM ingestion_file WHERE file_hash = :file_hash"),
            {'file_hash': file_hash}
        ).fetchone()
        
        if existing:
            return existing[0]
        
        # Insert new file record
        query = text("""
            INSERT INTO ingestion_file (
                org_code, investor_code, source_system, source_uri, 
                file_name, file_hash, received_at, metadata
            ) VALUES (
                :org_code, :investor_code, :source_system, :source_uri,
                :file_name, :file_hash, CURRENT_TIMESTAMP, :metadata
            )
            RETURNING file_id
        """)
        
        metadata = {
            'file_size': file_path.stat().st_size,
            'file_ext': file_path.suffix.lower(),
            'modified_time': file_path.stat().st_mtime
        }
        
        result = self.db.execute(query, {
            'org_code': org_code,
            'investor_code': investor_code,
            'source_system': source_system,
            'source_uri': str(file_path.absolute()),
            'file_name': file_path.name,
            'file_hash': file_hash,
            'metadata': metadata
        }).fetchone()
        
        return result[0] if result else None
    
    def create_job(self, file_id: int, pipeline_config: Dict[str, Any] = None) -> int:
        """
        Create processing job for file.
        Returns job_id.
        """
        query = text("""
            INSERT INTO ingestion_job (
                file_id, status, pipeline, created_at
            ) VALUES (
                :file_id, 'QUEUED', :pipeline, CURRENT_TIMESTAMP
            )
            RETURNING job_id
        """)
        
        result = self.db.execute(query, {
            'file_id': file_id,
            'pipeline': pipeline_config or {}
        }).fetchone()
        
        return result[0] if result else None
    
    def update_job_status(self, job_id: int, status: str, error_message: str = None, 
                         logs: List[str] = None):
        """Update job status and logs."""
        update_fields = ["status = :status"]
        params = {'job_id': job_id, 'status': status}
        
        if status == 'RUNNING':
            update_fields.append("started_at = CURRENT_TIMESTAMP")
        elif status in ['DONE', 'ERROR']:
            update_fields.append("finished_at = CURRENT_TIMESTAMP")
        
        if error_message:
            update_fields.append("error_message = :error_message")
            params['error_message'] = error_message
        
        if logs:
            update_fields.append("logs = :logs")
            params['logs'] = logs
        
        query = text(f"""
            UPDATE ingestion_job 
            SET {', '.join(update_fields)}
            WHERE job_id = :job_id
        """)
        
        self.db.execute(query, params)
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get jobs with QUEUED or ERROR status."""
        query = text("""
            SELECT 
                j.job_id, j.file_id, j.status, j.error_message, j.created_at,
                f.org_code, f.investor_code, f.file_name, f.source_uri
            FROM ingestion_job j
            JOIN ingestion_file f ON j.file_id = f.file_id
            WHERE j.status IN ('QUEUED', 'ERROR')
            ORDER BY j.created_at
        """)
        
        results = self.db.execute(query).fetchall()
        
        columns = ['job_id', 'file_id', 'status', 'error_message', 'created_at',
                  'org_code', 'investor_code', 'file_name', 'source_uri']
        
        return [dict(zip(columns, row)) for row in results]
    
    def get_file_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Get file record by hash."""
        query = text("""
            SELECT file_id, org_code, investor_code, source_uri, file_name, metadata
            FROM ingestion_file 
            WHERE file_hash = :file_hash
        """)
        
        result = self.db.execute(query, {'file_hash': file_hash}).fetchone()
        
        if result:
            columns = ['file_id', 'org_code', 'investor_code', 'source_uri', 'file_name', 'metadata']
            return dict(zip(columns, result))
        
        return None
    
    def scan_directory(self, directory_path: str, org_code: str, investor_code: str) -> List[str]:
        """
        Scan directory for new files (by hash).
        Returns list of new file paths.
        """
        directory = Path(directory_path)
        if not directory.exists():
            return []
        
        new_files = []
        
        # Supported file extensions
        supported_extensions = {'.pdf', '.xlsx', '.xls', '.csv'}
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                try:
                    if not self.is_file_processed(str(file_path)):
                        new_files.append(str(file_path))
                except Exception as e:
                    print(f"Error checking file {file_path}: {e}")
                    continue
        
        return new_files
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        query = text("""
            SELECT 
                COUNT(*) as total_files,
                COUNT(CASE WHEN j.status = 'DONE' THEN 1 END) as processed,
                COUNT(CASE WHEN j.status = 'QUEUED' THEN 1 END) as queued,
                COUNT(CASE WHEN j.status = 'ERROR' THEN 1 END) as errors,
                COUNT(CASE WHEN j.status = 'RUNNING' THEN 1 END) as running
            FROM ingestion_file f
            LEFT JOIN ingestion_job j ON f.file_id = j.file_id
        """)
        
        result = self.db.execute(query).fetchone()
        
        if result:
            return {
                'total_files': result[0] or 0,
                'processed': result[1] or 0,
                'queued': result[2] or 0,
                'errors': result[3] or 0,
                'running': result[4] or 0
            }
        
        return {'total_files': 0, 'processed': 0, 'queued': 0, 'errors': 0, 'running': 0}

def create_file_ledger(db: Session) -> FileLedger:
    """Create file ledger instance."""
    return FileLedger(db)