"""ChromaDB vector backend implementation."""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import chromadb
import openai
from chromadb.config import Settings as ChromaSettings

from app.config import load_settings

from .base import VectorBackend

logger = logging.getLogger(__name__)
settings = load_settings()


class ChromaVectorBackend(VectorBackend):
    """ChromaDB implementation of vector backend."""
    
    def __init__(self):
        """Initialize ChromaDB client."""
        self.chroma_dir = os.getenv("CHROMA_DIR", "./data/chroma")
        
        # Initialize ChromaDB persistent client
        self.client = chromadb.PersistentClient(
            path=self.chroma_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection_name = "pe_documents"
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "PE document embeddings"}
            )
        
        # Initialize OpenAI for embeddings
        api_key = os.getenv("OPENAI_API_KEY") or settings.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for embeddings")
        self.openai_client = openai.OpenAI(api_key=api_key)
        
        logger.info(f"ChromaDB backend initialized with collection: {self.collection_name}")
    
    async def add(self, text: str, metadata: Dict[str, Any]) -> str:
        """Add a single chunk to ChromaDB."""
        chunk_id = str(uuid.uuid4())
        
        # Create embedding
        embedding_response = self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-large"
        )
        embedding = embedding_response.data[0].embedding
        
        # Add to ChromaDB
        self.collection.add(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
        
        return chunk_id
    
    async def add_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """Add multiple chunks for a document."""
        if not chunks:
            return []
        
        chunk_ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        # Prepare batch embedding request
        texts = [chunk['text'] for chunk in chunks]
        
        # Create embeddings in batch
        embedding_response = self.openai_client.embeddings.create(
            input=texts,
            model="text-embedding-3-large"
        )
        
        # Prepare data for ChromaDB
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_ids.append(chunk_id)
            embeddings.append(embedding_response.data[i].embedding)
            documents.append(chunk['text'])
            
            # Prepare metadata
            chunk_metadata = chunk.get('metadata', {})
            chunk_metadata.update({
                'doc_id': doc_id,
                'chunk_index': i,
                'doc_type': chunk.get('doc_type', 'unknown')
            })
            metadatas.append(chunk_metadata)
        
        # Add to ChromaDB in batch
        self.collection.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(chunk_ids)} chunks to ChromaDB for document {doc_id}")
        return chunk_ids
    
    async def query(
        self, 
        query_text: str, 
        n_results: int = 5, 
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query ChromaDB for similar chunks."""
        
        # Create query embedding
        embedding_response = self.openai_client.embeddings.create(
            input=query_text,
            model="text-embedding-3-large"
        )
        query_embedding = embedding_response.data[0].embedding
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results
        return {
            'documents': results['documents'][0] if results['documents'] else [],
            'metadatas': results['metadatas'][0] if results['metadatas'] else [],
            'distances': results['distances'][0] if results['distances'] else [],
            'ids': results['ids'][0] if results['ids'] else []
        }
    
    async def delete(self, chunk_id: str) -> bool:
        """Delete a chunk from ChromaDB."""
        try:
            self.collection.delete(ids=[chunk_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
            return False
    
    async def count(self) -> int:
        """Get total number of chunks in ChromaDB."""
        return self.collection.count()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB health."""
        try:
            count = await self.count()
            return {
                'status': 'healthy',
                'backend': 'chromadb',
                'collection': self.collection_name,
                'chunk_count': count,
                'path': self.chroma_dir
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'backend': 'chromadb',
                'error': str(e)
            }