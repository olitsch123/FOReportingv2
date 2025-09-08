"""Check OpenAI vector store after document processing."""

import os
import openai
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Load environment variables
load_dotenv()

def check_vector_store_status():
    """Check OpenAI vector store status and contents."""
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
        
        print(f"🔍 OpenAI Vector Store Status")
        print(f"   Store ID: {vector_store_id}")
        print("=" * 60)
        
        # Get vector store info
        vs = client.vector_stores.retrieve(vector_store_id)
        
        print(f"\n📊 Vector Store Info:")
        print(f"   - Name: {vs.name}")
        print(f"   - Status: {vs.status}")
        print(f"   - Created: {datetime.fromtimestamp(vs.created_at) if hasattr(vs, 'created_at') and vs.created_at else 'N/A'}")
        print(f"\n📁 File Statistics:")
        print(f"   - Total Files: {vs.file_counts.total}")
        print(f"   - Completed: {vs.file_counts.completed}")
        print(f"   - In Progress: {vs.file_counts.in_progress}")
        print(f"   - Failed: {vs.file_counts.failed}")
        print(f"   - Cancelled: {vs.file_counts.cancelled}")
        print(f"\n💾 Storage:")
        print(f"   - Size: {vs.usage_bytes:,} bytes ({vs.usage_bytes / 1024 / 1024:.2f} MB)")
        
        # List recent files
        print("\n📄 Files in Vector Store:")
        print("-" * 60)
        
        files = client.vector_stores.files.list(
            vector_store_id=vector_store_id,
            limit=50
        )
        
        if files.data:
            for i, file in enumerate(files.data, 1):
                print(f"\n{i}. File ID: {file.id}")
                print(f"   Status: {file.status}")
                if hasattr(file, 'created_at'):
                    print(f"   Created: {datetime.fromtimestamp(file.created_at)}")
                
                # Try to get file info
                try:
                    file_info = client.files.retrieve(file.id)
                    print(f"   Filename: {file_info.filename}")
                    print(f"   Size: {file_info.bytes:,} bytes")
                    print(f"   Purpose: {file_info.purpose}")
                except:
                    print(f"   (Could not retrieve file details)")
        else:
            print("   ❌ No files found in vector store")
            
        return vs.file_counts.total > 0
            
    except Exception as e:
        print(f"\n❌ Error accessing vector store: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_pe_document_embeddings():
    """Check PE document embedding status in database."""
    try:
        from app.database.connection import get_db
        from sqlalchemy import text
        
        print("\n\n📊 Database Embedding Status")
        print("=" * 60)
        
        with get_db() as db:
            # Check pe_document embedding status
            result = db.execute(text("""
                SELECT 
                    embedding_status,
                    COUNT(*) as count,
                    SUM(COALESCE(chunk_count, 0)) as total_chunks
                FROM pe_document
                GROUP BY embedding_status
            """))
            
            print("\nPE Document Embedding Status:")
            total_docs = 0
            for row in result:
                status = row.embedding_status or 'not_started'
                count = row.count
                chunks = row.total_chunks or 0
                total_docs += count
                print(f"   - {status}: {count} documents ({chunks} chunks)")
            
            if total_docs == 0:
                print("   ❌ No PE documents found")
            
            # Show recent documents with embeddings
            result = db.execute(text("""
                SELECT 
                    doc_id,
                    file_name,
                    doc_type,
                    embedding_status,
                    chunk_count,
                    embedding_error,
                    upload_date
                FROM pe_document
                WHERE embedding_status IS NOT NULL
                ORDER BY upload_date DESC
                LIMIT 10
            """))
            
            rows = list(result)
            if rows:
                print("\n📄 Recent Documents with Embedding Status:")
                for i, row in enumerate(rows, 1):
                    print(f"\n{i}. {row.file_name}")
                    print(f"   Doc ID: {row.doc_id}")
                    print(f"   Type: {row.doc_type}")
                    print(f"   Embedding Status: {row.embedding_status}")
                    print(f"   Chunks: {row.chunk_count or 0}")
                    if row.embedding_error:
                        print(f"   Error: {row.embedding_error}")
                        
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        import traceback
        traceback.print_exc()

async def test_search_functionality():
    """Test searching the vector store."""
    try:
        from app.pe_docs.storage.vector import PEVectorStore
        
        print("\n\n🔍 Testing Vector Search")
        print("=" * 60)
        
        store = PEVectorStore()
        
        # Test queries
        test_queries = [
            "capital account",
            "fund investor",
            "quarterly report",
            "financial statement"
        ]
        
        for query in test_queries:
            print(f"\n📌 Searching for: '{query}'")
            
            results = await store.search(
                query=query,
                top_k=3
            )
            
            if results:
                print(f"   ✅ Found {len(results)} results")
                for i, result in enumerate(results, 1):
                    print(f"\n   Result {i}:")
                    print(f"      Score: {result.get('score', 'N/A')}")
                    print(f"      Text: {result.get('text', '')[:150]}...")
                    metadata = result.get('metadata', {})
                    print(f"      File: {metadata.get('filename', 'N/A')}")
            else:
                print(f"   ❌ No results found")
                
    except Exception as e:
        print(f"\n❌ Search error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("OpenAI Vector Store Check - After Processing")
    print("=" * 60)
    
    # Check vector store
    has_files = check_vector_store_status()
    
    # Check database
    check_pe_document_embeddings()
    
    # Test search if files exist
    if has_files:
        print("\n🔄 Running search tests...")
        asyncio.run(test_search_functionality())
    else:
        print("\n⚠️  No files in vector store - skipping search tests")
    
    print("\n" + "=" * 60)
    print("✅ Check complete!")
    print("=" * 60)