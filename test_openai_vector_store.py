"""Test OpenAI vector store after document processing."""

import os
import openai
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

def check_vector_store_contents():
    """Check OpenAI vector store contents."""
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
        
        print(f"🔍 Checking vector store: {vector_store_id}")
        
        # Get vector store info
        vs = client.vector_stores.retrieve(vector_store_id)
        print(f"\n✅ Vector Store Status:")
        print(f"  - Name: {vs.name}")
        print(f"  - Status: {vs.status}")
        print(f"  - Total Files: {vs.file_counts.total}")
        print(f"  - Completed: {vs.file_counts.completed}")
        print(f"  - In Progress: {vs.file_counts.in_progress}")
        print(f"  - Failed: {vs.file_counts.failed}")
        print(f"  - Size: {vs.usage_bytes:,} bytes")
        
        # List files in vector store
        print("\n📄 Files in vector store:")
        files = client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=20
        )
        
        if files.data:
            for i, file in enumerate(files.data):
                print(f"  {i+1}. File ID: {file.id}")
                print(f"     Status: {file.status}")
                if hasattr(file, 'created_at'):
                    print(f"     Created: {file.created_at}")
        else:
            print("  ❌ No files found in vector store")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_vector_search():
    """Test searching the vector store."""
    try:
        from app.pe_docs.storage.vector import PEVectorStore
        
        print("\n🔍 Testing vector search...")
        store = PEVectorStore()
        
        # Test search
        results = await store.search(
            query="capital account fund investor",
            top_k=5
        )
        
        print(f"\n📊 Search Results: {len(results)} found")
        for i, result in enumerate(results):
            print(f"\n  Result {i+1}:")
            print(f"    Score: {result.get('score', 'N/A')}")
            print(f"    Text: {result.get('text', '')[:200]}...")
            print(f"    Metadata: {result.get('metadata', {})}")
            
    except Exception as e:
        print(f"❌ Search error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("OpenAI Vector Store Test")
    print("=" * 60)
    
    check_vector_store_contents()
    asyncio.run(test_vector_search())
    
    print("\n" + "=" * 60)