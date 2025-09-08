"""File system watcher service."""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Set

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import get_investor_from_path, load_settings
from app.database.connection import get_db

settings = load_settings()
from app.database.document_tracker import DocumentTrackerService, calculate_file_hash
from app.pe_docs.api.processing import handle_file as pe_handle_file
from app.processors.processor_factory import ProcessorFactory
from app.services.document_service import DocumentService

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
        path_obj = Path(file_path)
        
        # Check exclusion rules
        # 1. Skip Python scripts
        if path_obj.suffix.lower() == '.py':
            logger.debug(f"Skipping Python script: {file_path}")
            return
        
        # 2. Skip files matching [Date]_Fund_Documents.xlsx pattern
        if path_obj.name.endswith('_Fund_Documents.xlsx') and '[' in path_obj.name:
            logger.debug(f"Skipping Fund Documents file: {file_path}")
            return
        
        # 3. Skip files in folders starting with "!"
        for parent in path_obj.parents:
            if parent.name.startswith('!'):
                logger.debug(f"Skipping file in excluded folder (!{parent.name}): {file_path}")
                return
        
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
        db = next(get_db())
        tracker_service = DocumentTrackerService(db)
        file_hash = None
        
        try:
            logger.info(f"Processing file: {file_path}")
            
            # Check if file still exists
            if not Path(file_path).exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Track the document
            doc_tracker = tracker_service.track_document(file_path)
            if not doc_tracker:
                logger.error(f"Failed to track document: {file_path}")
                return
            
            file_hash = doc_tracker.file_hash
            
            # Check if already processed
            if doc_tracker.status == 'completed':
                logger.info(f"File already processed (hash: {file_hash[:8]}...): {file_path}")
                return
            
            # Mark as processing
            tracker_service.mark_processing(file_hash)
            
            # Determine investor
            investor_code = get_investor_from_path(file_path)
            if not investor_code:
                logger.warning(f"Could not determine investor for file: {file_path}")
                tracker_service.mark_failed(file_hash, "Could not determine investor")
                return
            
            # Process via PE docs API
            try:
                result = await pe_handle_file(file_path, investor_code, db)
                
                if result:
                    # Extract metadata from result if available
                    metadata = {
                        'investor_name': investor_code,
                        'document_type': getattr(result, 'doc_type', None) if hasattr(result, 'doc_type') else None,
                        'fund_name': getattr(result, 'fund_name', None) if hasattr(result, 'fund_name') else None,
                    }
                    
                    # Mark as completed
                    pe_doc_id = getattr(result, 'id', None) if hasattr(result, 'id') else None
                    tracker_service.mark_completed(file_hash, pe_document_id=pe_doc_id, metadata=metadata)
                    logger.info(f"Successfully processed: {file_path} (hash: {file_hash[:8]}...)")
                else:
                    tracker_service.mark_failed(file_hash, "Processing returned no result")
                    logger.error(f"Failed to process: {file_path}")
                    
            except Exception as e:
                logger.error(f"PE docs processing failed: {e}")
                
                # Try fallback to original document service
                try:
                    result = await self.document_service.process_document(
                        file_path=file_path,
                        investor_code=investor_code
                    )
                    
                    if result:
                        doc_id = result.get('id') if isinstance(result, dict) else None
                        tracker_service.mark_completed(file_hash, document_id=doc_id)
                        logger.info(f"Successfully processed via fallback: {file_path}")
                    else:
                        tracker_service.mark_failed(file_hash, f"Fallback processing failed: {str(e)}")
                        logger.error(f"Fallback also failed: {file_path}")
                        
                except Exception as fallback_error:
                    tracker_service.mark_failed(file_hash, f"All processing failed: {str(e)} / {str(fallback_error)}")
                    logger.error(f"All processing attempts failed for {file_path}: {str(fallback_error)}")
                    
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            if file_hash:
                tracker_service.mark_failed(file_hash, str(e))
        finally:
            db.close()
    
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
            investor1_path = os.getenv("INVESTOR1_PATH")
            investor2_path = os.getenv("INVESTOR2_PATH")
                
            folders_to_watch = [
                ("Investor 1", investor1_path),
                ("Investor 2", investor2_path),
            ]
            
            folders_watched = 0
            for name, folder in folders_to_watch:
                if not folder:
                    logger.warning(f"{name}: Folder not configured (ENV missing)")
                    continue
                try:
                    folder_path = Path(folder)
                except (TypeError, ValueError):
                    logger.warning(f"{name}: Invalid folder path (None or malformed)")
                    continue
                if folder_path.exists():
                    self.observer.schedule(
                        self.handler,
                        str(folder_path),
                        recursive=True
                    )
                    logger.info(f"Watching {name}: {folder}")
                    folders_watched += 1
                else:
                    logger.warning(f"{name}: Folder does not exist: {folder}")
            
            if folders_watched == 0:
                logger.warning("No valid folders to watch!")
            
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
        
        # Get paths
        investor1_path = os.getenv("INVESTOR1_PATH")
        investor2_path = os.getenv("INVESTOR2_PATH")
            
        folders_to_scan = [
            ("Investor 1", investor1_path),
            ("Investor 2", investor2_path),
        ]
        
        total_files_queued = 0
        for name, folder in folders_to_scan:
            if not folder:
                continue
            try:
                folder_path = Path(folder)
            except (TypeError, ValueError):
                continue
            if not folder_path.exists():
                logger.warning(f"Cannot scan {name}: folder does not exist")
                continue
            
            # Find all supported files
            supported_extensions = self.handler.processor_factory.get_supported_extensions()
            
            files_in_folder = 0
            files_skipped = 0
            for ext in supported_extensions:
                # Skip Python files
                if ext.lower() == '.py':
                    continue
                    
                pattern = f"**/*{ext}"
                for file_path in folder_path.rglob(pattern):
                    if file_path.is_file():
                        # Apply exclusion rules
                        # 1. Skip Python scripts (redundant but safe)
                        if file_path.suffix.lower() == '.py':
                            files_skipped += 1
                            continue
                        
                        # 2. Skip files matching [Date]_Fund_Documents.xlsx pattern
                        if file_path.name.endswith('_Fund_Documents.xlsx') and '[' in file_path.name:
                            files_skipped += 1
                            continue
                        
                        # 3. Skip files in folders starting with "!"
                        skip_file = False
                        for parent in file_path.parents:
                            if parent.name.startswith('!'):
                                skip_file = True
                                break
                        if skip_file:
                            files_skipped += 1
                            continue
                        
                        # Schedule for processing (with small delay to spread load)
                        await asyncio.sleep(0.1)
                        self.handler._queue_file_for_processing(str(file_path), "existing")
                        files_in_folder += 1
            
            logger.info(f"Queued {files_in_folder} files from {name} (skipped {files_skipped} excluded files)")
            total_files_queued += files_in_folder
        
        logger.info(f"Finished queuing {total_files_queued} existing files for processing")
    
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