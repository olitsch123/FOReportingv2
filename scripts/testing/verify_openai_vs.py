"""Verify OpenAI Vector Store is accessible."""

import logging
import os

import openai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def main():
    """Main verification function."""
    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")

    logger.info(f"API Key: {'✅ Set' if api_key else '❌ Not set'}")
    logger.info(f"Vector Store ID: {vector_store_id if vector_store_id else '❌ Not set'}")

    if api_key and vector_store_id:
        try:
            client = openai.OpenAI(api_key=api_key)
            vs = client.beta.vector_stores.retrieve(vector_store_id)
            logger.info("✅ Vector Store Access Successful!")
            logger.info(f"  Name: {vs.name}")
            logger.info(f"  Status: {vs.status}")
            logger.info(f"  Files: {vs.file_counts.total}")
            logger.info(f"  Size: {vs.usage_bytes:,} bytes")
            
            # List a few files
            logger.info("📄 Sample files:")
            files = client.beta.vector_stores.files.list(vector_store_id=vector_store_id, limit=5)
            for f in files.data:
                logger.info(f"  - {f.id}: {f.status}")
                
        except Exception as e:
            logger.error(f"❌ Error accessing vector store: {e}")
    else:
        logger.error("Missing required environment variables")

if __name__ == "__main__":
    main()