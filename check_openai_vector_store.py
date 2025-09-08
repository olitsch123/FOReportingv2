"""Check OpenAI vector store status and contents."""

import os
import openai
from dotenv import load_dotenv
import asyncio
from app.pe_docs.storage.vector import PEVectorStore

# Load environment variables
load_dotenv()

def check_vector_store():
    """Check OpenAI vector store."""
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
        
        if not vector_store_id:
            print("❌ OPENAI_VECTOR_STORE_ID not set in environment")
            return
        
        print(f"Checking vector store: {vector_store_id}")
        
        # Get vector store info
        try:
            vs = client.beta.vector_stores.retrieve(vector_store_id)
            print(f"\n✅ Vector Store Found:")
            print(f"  - ID: {vs.id}")
            print(f"  - Name: {vs.name}")
            print(f"  - Status: {vs.status}")
            print(f"  - File Count: {vs.file_counts.total}")
            print(f"  - In Progress: {vs.file_counts.in_progress}")
            print(f"  - Completed: {vs.file_counts.completed}")
            print(f"  - Failed: {vs.file_counts.failed}")
            print(f"  - Bytes: {vs.usage_bytes:,}")
            
            # List files in vector store
            print("\n📄 Files in vector store:")
            files = client.beta.vector_stores.files.list(
                vector_store_id=vector_store_id,
                limit=10
            )
            
            if files.data:
                for file in files.data:
                    print(f"  - File ID: {file.id}, Status: {file.status}")
            else:
                print("  No files found in vector store")
                
        except Exception as e:
            print(f"❌ Error accessing vector store: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

async def test_pe_vector_store():
    """Test PEVectorStore initialization and stats."""
    try:
        print("\n🔧 Testing PEVectorStore...")
        store = PEVectorStore()
        stats = await store.get_stats()
        print(f"PEVectorStore stats: {stats}")
    except Exception as e:
        print(f"❌ PEVectorStore error: {e}")

if __name__ == "__main__":
    check_vector_store()
    asyncio.run(test_pe_vector_store())