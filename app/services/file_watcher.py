"""File system watcher service."""

import asyncio
import logging
from pathlib import Path
from typing import Set, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from app.config import load_settings, get_investor_from_path
from app.database.connection import get_db
import os

settings = load_settings()
from app.services.document_service import DocumentService
from app.processors.processor_factory import ProcessorFactory
from app.pe_docs.api import handle_file as pe_handle_file
# from app.pe_docs.storage.ledger import create_file_ledger  # TODO: Re-enable when storage modules restored

logger = logging.getLogger(__name__)


class DocumentFileHandler(FileSystemEventHandler):
    """File system event handler for document processing."""
    
    def __init__(self, document_service: DocumentService):
        """Initialize the handler."""
        super().__init__()
        self.document_service = document_service
        self.processor_factory = ProcessorFactory()
        self.processing_queue: Set[str] = set()
        self.file_timestamps: Dict[str, datetime] = {}
        self.debounce_seconds = 5  # Wait 5 seconds before processing
        
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            self._queue_file_for_processing(event.src_path, "created")
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory:
            self._queue_file_for_processing(event.src_path, "modified")
    
    def _queue_file_for_processing(self, file_path: str, event_type: str):
        """Queue a file for processing with debouncing."""
        file_path = str(Path(file_path).absolute())
        
        # Check if file extension is supported
        if not self.processor_factory.can_process_file(file_path):
            logger.debug(f"Skipping unsupported file: {file_path}")
            return
        
        # Check file size (skip if too large)
        try:
            file_size = Path(file_path).stat().st_size
            max_size = settings.get("MAX_FILE_SIZE_MB", 100) * 1024 * 1024
            if file_size > max_size:
                logger.warning(f"File too large ({file_size} bytes): {file_path}")
                return
        except OSError:
            logger.warning(f"Cannot access file: {file_path}")
            return
        
        # Debounce: update timestamp and schedule processing
        current_time = datetime.now()
        self.file_timestamps[file_path] = current_time
        
        logger.info(f"File {event_type}: {file_path}")
        
        # Schedule processing after debounce period
        asyncio.create_task(self._process_file_after_delay(file_path))
    
    async def _process_file_after_delay(self, file_path: str):
        """Process file after debounce delay."""
        await asyncio.sleep(self.debounce_seconds)
        
        # Check if file was modified again during debounce period
        if file_path in self.file_timestamps:
            last_timestamp = self.file_timestamps[file_path]
            if datetime.now() - last_timestamp < timedelta(seconds=self.debounce_seconds - 1):
                # File was modified recently, skip this processing
                return
        
        # Remove from timestamps and process
        self.file_timestamps.pop(file_path, None)
        
        if file_path not in self.processing_queue:
            self.processing_queue.add(file_path)
            try:
                await self._process_file(file_path)
            finally:
                self.processing_queue.discard(file_path)
    
    async def _process_file(self, file_path: str):
        """Process a single file."""
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Check if file still exists
            if not Path(file_path).exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Check if file is already being processed or recently processed
            existing_doc = await self.document_service.get_document_by_path(file_path)
            if existing_doc:
                # Check if file has changed (compare hash)
                current_hash = self._calculate_file_hash(file_path)
                if existing_doc.file_hash == current_hash:
                    logger.info(f"File unchanged, skipping: {file_path}")
                    return
                
                logger.info(f"File changed, reprocessing: {file_path}")
            
            # Determine investor
            investor_code = get_investor_from_path(file_path)
            if not investor_code:
                logger.warning(f"Could not determine investor for file: {file_path}")
                return
            
            # Process via PE docs API
            db = next(get_db())
            try:
                await pe_handle_file(file_path, "default", investor_code, db)
                result = True
            except Exception as e:
                logger.error(f"PE docs processing failed: {e}")
                # Fallback to original document service
                result = await self.document_service.process_document(
                    file_path=file_path,
                    investor_code=investor_code
                )
            finally:
                db.close()
            
            if result:
                logger.info(f"Successfully processed: {file_path}")
            else:
                logger.error(f"Failed to process: {file_path}")
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""


class FileWatcherService:
    """File watcher service for monitoring investor folders."""
    
    def __init__(self, document_service: DocumentService):
        """Initialize the file watcher service."""
        self.document_service = document_service
        self.observer = Observer()
        self.handler = DocumentFileHandler(document_service)
        self.is_running = False
        
    async def start(self):
        """Start watching the configured folders."""
        if self.is_running:
            logger.warning("File watcher is already running")
            return
        
        try:
            # Watch investor folders
            folders_to_watch = [
                os.getenv("INVESTOR1_PATH"),
                os.getenv("INVESTOR2_PATH"),
            ]
            
            for folder in folders_to_watch:
                folder_path = Path(folder)
                if folder_path.exists():
                    self.observer.schedule(
                        self.handler,
                        str(folder_path),
                        recursive=True
                    )
                    logger.info(f"Watching folder: {folder}")
                else:
                    logger.warning(f"Folder does not exist: {folder}")
            
            # Start the observer
            self.observer.start()
            self.is_running = True
            logger.info("File watcher service started")
            
            # Process existing files on startup
            await self._process_existing_files()
            
        except Exception as e:
            logger.error(f"Error starting file watcher: {str(e)}")
            raise
    
    async def stop(self):
        """Stop the file watcher service."""
        if not self.is_running:
            return
        
        try:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            logger.info("File watcher service stopped")
        except Exception as e:
            logger.error(f"Error stopping file watcher: {str(e)}")
    
    async def _process_existing_files(self):
        """Process existing files in watched folders on startup."""
        logger.info("Processing existing files...")
        
        folders_to_scan = [
            os.getenv("INVESTOR1_PATH"),
            os.getenv("INVESTOR2_PATH"),
        ]
        
        for folder in folders_to_scan:
            folder_path = Path(folder)
            if not folder_path.exists():
                continue
            
            # Find all supported files
            supported_extensions = self.handler.processor_factory.get_supported_extensions()
            
            for ext in supported_extensions:
                pattern = f"**/*{ext}"
                for file_path in folder_path.rglob(pattern):
                    if file_path.is_file():
                        # Schedule for processing (with small delay to spread load)
                        await asyncio.sleep(0.1)
                        self.handler._queue_file_for_processing(str(file_path), "existing")
        
        logger.info("Finished queuing existing files for processing")
    
    async def rescan_pe_paths(self):
        """Rescan PE investor paths for new files."""
        logger.info("Rescanning PE investor paths...")
        
        db = next(get_db())
        try:
            ledger = create_file_ledger(db)
            
            investor1_path = settings.get('INVESTOR1_PATH')
            investor2_path = settings.get('INVESTOR2_PATH')
            
            total_new = 0
            
            if investor1_path and Path(investor1_path).exists():
                new_files = ledger.scan_directory(investor1_path, "brainweb", "brainweb")
                logger.info(f"INVESTOR1_PATH: found {len(new_files)} new files")
                
                for file_path in new_files:
                    try:
                        await pe_handle_file(file_path, "brainweb", "brainweb", db)
                        total_new += 1
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
            
            if investor2_path and Path(investor2_path).exists():
                new_files = ledger.scan_directory(investor2_path, "pecunalta", "pecunalta")
                logger.info(f"INVESTOR2_PATH: found {len(new_files)} new files")
                
                for file_path in new_files:
                    try:
                        await pe_handle_file(file_path, "pecunalta", "pecunalta", db)
                        total_new += 1
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
            
            db.commit()
            logger.info(f"PE rescan completed: {total_new} new files processed")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error during PE rescan: {e}")
        finally:
            db.close()
    
    async def process_single_file(self, file_path: str) -> bool:
        """Process a single file manually."""
        try:
            await self.handler._process_file(file_path)
            return True
        except Exception as e:
            logger.error(f"Error processing single file {file_path}: {str(e)}")
            return False