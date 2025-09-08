"""Standalone runner for the file watcher service."""

import asyncio
import logging
import os

from app.services.document_service import DocumentService
from app.services.file_watcher import FileWatcherService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    enable_watcher = os.getenv("ENABLE_FILE_WATCHER", "true").lower() == "true"
    if not enable_watcher:
        logger.info("File watcher disabled by ENABLE_FILE_WATCHER=false")
        return

    document_service = DocumentService()
    watcher = FileWatcherService(document_service)
    await watcher.start()

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping watcher...")
        await watcher.stop()


def run_watcher():
    """Synchronous entry point for running the watcher."""
    asyncio.run(main())


if __name__ == "__main__":
    run_watcher()

