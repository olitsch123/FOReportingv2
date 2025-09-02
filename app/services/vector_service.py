"""Vector database service for document embeddings."""

import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid
import chromadb
from chromadb.config import Settings
import openai

from app.config import settings

logger = logging.getLogger(__name__)


class VectorService:
    """Service for managing document embeddings and vector search."""
    
    def __init__(self):
        """Initialize the vector service."""
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection_name = "documents"
        try:
            self.collection = self.chroma_client.get_collection(self.collection_name)
        except ValueError:
            # Collection doesn't exist, create it
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Financial document embeddings"}
            )
        
        logger.info(f"Vector service initialized with collection: {self.collection_name}")
    
    async def add_document(
        self, 
        document_id: str, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Add a document chunk to the vector store."""
        try:
            # Generate embedding
            embedding = await self._create_embedding(text)
            if not embedding:
                return None
            
            # Create unique ID for this chunk
            chunk_id = str(uuid.uuid4())
            
            # Prepare metadata
            chunk_metadata = {
                "document_id": document_id,
                "text_length": len(text),
                "chunk_id": chunk_id,
                **(metadata or {})
            }
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[chunk_metadata],
                ids=[chunk_id]
            )
            
            logger.debug(f"Added document chunk to vector store: {chunk_id}")
            return chunk_id
            
        except Exception as e:
            logger.error(f"Error adding document to vector store: {str(e)}")
            return None
    
    async def search_documents(
        self, 
        query: str, 
        limit: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity."""
        try:
            # Generate query embedding
            query_embedding = await self._create_embedding(query)
            if not query_embedding:
                return []
            
            # Prepare where clause for filtering
            where_clause = None
            if filter_metadata:
                where_clause = filter_metadata
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_clause,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            search_results = []
            if results['documents'] and len(results['documents']) > 0:
                for i in range(len(results['documents'][0])):
                    result = {
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0,
                        'similarity': 1.0 - results['distances'][0][i] if results['distances'] else 1.0
                    }
                    search_results.append(result)
            
            logger.debug(f"Vector search returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching vector store: {str(e)}")
            return []
    
    async def get_document_context(
        self, 
        document_ids: List[str], 
        query: str,
        max_chunks: int = 5
    ) -> List[Dict[str, Any]]:
        """Get relevant context from specific documents for a query."""
        try:
            # Search within specific documents
            filter_metadata = {"document_id": {"$in": document_ids}}
            
            results = await self.search_documents(
                query=query,
                limit=max_chunks,
                filter_metadata=filter_metadata
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting document context: {str(e)}")
            return []
    
    async def remove_document(self, document_id: str) -> bool:
        """Remove all chunks for a document from the vector store."""
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(
                where={"document_id": document_id},
                include=["metadatas"]
            )
            
            if results['ids']:
                # Delete all chunks
                self.collection.delete(ids=results['ids'])
                logger.info(f"Removed {len(results['ids'])} chunks for document: {document_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error removing document from vector store: {str(e)}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        try:
            count = self.collection.count()
            
            # Get sample of documents to analyze
            sample_results = self.collection.get(
                limit=min(100, count),
                include=["metadatas"]
            )
            
            # Analyze document types and sources
            document_types = {}
            document_sources = set()
            
            for metadata in sample_results.get('metadatas', []):
                doc_id = metadata.get('document_id')
                if doc_id:
                    document_sources.add(doc_id)
                
                doc_type = metadata.get('document_type', 'unknown')
                document_types[doc_type] = document_types.get(doc_type, 0) + 1
            
            return {
                'total_chunks': count,
                'unique_documents': len(document_sources),
                'document_types': document_types,
                'collection_name': self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {}
    
    async def _create_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding for text using OpenAI."""
        try:
            # Clean and truncate text if necessary
            cleaned_text = text.strip()
            if not cleaned_text:
                return None
            
            # Truncate if too long (OpenAI has token limits)
            max_length = 8000  # Conservative limit
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length]
            
            # Create embedding
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=cleaned_text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            return None
    
    async def reset_collection(self) -> bool:
        """Reset the entire collection (for development/testing)."""
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Financial document embeddings"}
            )
            logger.info("Vector collection reset successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting collection: {str(e)}")
            return False