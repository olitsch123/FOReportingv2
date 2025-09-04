#!/usr/bin/env python3
"""Production startup script for FOReporting v2."""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Set UTF-8 environment
os.environ['PYTHONUTF8'] = '1'
os.environ['PGCLIENTENCODING'] = 'UTF8'

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_services():
    """Test all services before starting."""
    logger.info("🧪 Testing production services...")
    
    # Test configuration
    try:
        from app.config import settings
        logger.info(f"✅ Configuration loaded - Deployment mode: {settings.get('DEPLOYMENT_MODE')}")
    except Exception as e:
        logger.error(f"❌ Configuration failed: {e}")
        return False
    
    # Test file storage
    try:
        from app.database.file_storage import FileStorageService
        file_storage = FileStorageService()
        investors = file_storage.get_investors()
        logger.info(f"✅ File storage working - {len(investors)} investors")
    except Exception as e:
        logger.error(f"❌ File storage failed: {e}")
        return False
    
    # Test vector service
    try:
        from app.services.vector_service import VectorService
        vector_service = VectorService()
        logger.info("✅ Vector service initialized")
    except Exception as e:
        logger.error(f"❌ Vector service failed: {e}")
        return False
    
    return True

def start_server():
    """Start the production server."""
    if not test_services():
        logger.error("❌ Service tests failed - aborting startup")
        return
    
    logger.info("🚀 Starting FOReporting v2 Production Server...")
    
    try:
        import uvicorn
        from app.main import app
        
        # Production server settings
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload to avoid caching issues
            log_level="info",
            access_log=True
        )
        
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")

if __name__ == "__main__":
    start_server()