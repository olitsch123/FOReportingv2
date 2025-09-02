"""Test script for document processing functionality."""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.processors.processor_factory import ProcessorFactory
from app.services.document_service import DocumentService
from app.services.vector_service import VectorService
from app.database.connection import engine, Base


async def test_processors():
    """Test document processors."""
    print("🧪 Testing Document Processors")
    print("=" * 40)
    
    factory = ProcessorFactory()
    
    # Test supported extensions
    extensions = factory.get_supported_extensions()
    print(f"✅ Supported extensions: {extensions}")
    
    # Test file type detection
    test_files = [
        "test.pdf",
        "test.xlsx",
        "test.csv",
        "test.docx"  # Not supported
    ]
    
    for file in test_files:
        can_process = factory.can_process_file(file)
        status = "✅" if can_process else "❌"
        print(f"{status} {file}: {'Supported' if can_process else 'Not supported'}")


async def test_vector_service():
    """Test vector service functionality."""
    print("\n🧪 Testing Vector Service")
    print("=" * 40)
    
    try:
        vector_service = VectorService()
        
        # Test adding a document
        print("📄 Testing document embedding...")
        test_text = """
        This is a quarterly report for BrainWeb Fund I.
        NAV as of Q3 2023: €50,000,000
        IRR: 15.2%
        MOIC: 1.8x
        """
        
        doc_id = await vector_service.add_document(
            document_id="test-doc-1",
            text=test_text,
            metadata={"test": True}
        )
        
        if doc_id:
            print(f"✅ Document embedded successfully: {doc_id}")
        else:
            print("❌ Failed to embed document")
            return
        
        # Test search
        print("🔍 Testing semantic search...")
        results = await vector_service.search_documents(
            query="What is the NAV of BrainWeb Fund?",
            limit=5
        )
        
        if results:
            print(f"✅ Search returned {len(results)} results")
            for i, result in enumerate(results[:2]):
                print(f"  Result {i+1}: Similarity {result['similarity']:.3f}")
        else:
            print("❌ Search returned no results")
        
        # Test collection stats
        stats = await vector_service.get_collection_stats()
        print(f"📊 Collection stats: {stats}")
        
        # Cleanup
        await vector_service.remove_document("test-doc-1")
        print("🧹 Test document removed")
        
    except Exception as e:
        print(f"❌ Vector service test failed: {str(e)}")


async def test_document_service():
    """Test document service functionality."""
    print("\n🧪 Testing Document Service")
    print("=" * 40)
    
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        
        doc_service = DocumentService()
        
        # Test getting documents (should be empty initially)
        documents = await doc_service.get_documents(limit=5)
        print(f"📄 Found {len(documents)} existing documents")
        
        print("✅ Document service is working")
        
    except Exception as e:
        print(f"❌ Document service test failed: {str(e)}")


async def main():
    """Run all tests."""
    print("🚀 FOReporting v2 - Component Testing")
    print("=" * 50)
    
    try:
        # Test processors
        await test_processors()
        
        # Test vector service
        await test_vector_service()
        
        # Test document service
        await test_document_service()
        
        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Testing failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())