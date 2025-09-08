"""OpenAI Vector Store backend implementation."""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import httpx
import openai

from app.config import load_settings

from .base import VectorBackend

logger = logging.getLogger(__name__)
settings = load_settings()


class OpenAIVectorBackend(VectorBackend):
    """OpenAI Vector Store implementation of vector backend."""
    
    def __init__(self):
        """Initialize OpenAI Vector Store client."""
        api_key = os.getenv("OPENAI_API_KEY") or settings.get("OPENAI_API_KEY")
        vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID") or settings.get("OPENAI_VECTOR_STORE_ID")
        
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI vector backend")
        if not vector_store_id:
            raise ValueError("OPENAI_VECTOR_STORE_ID required for OpenAI vector backend")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.vector_store_id = vector_store_id
        self.http_client = httpx.AsyncClient()
        
        logger.info(f"OpenAI vector backend initialized with store: {vector_store_id}")
    
    async def add(self, text: str, metadata: Dict[str, Any]) -> str:
        """Add a single chunk to OpenAI Vector Store."""
        # For OpenAI Vector Store, we need to upload as a file
        # This is a simplified implementation - in practice you'd batch these
        chunk_id = str(uuid.uuid4())
        
        # Create a temporary file-like object
        import io
        file_content = f"# Document Chunk {chunk_id}\n\n{text}\n\n## Metadata\n{metadata}"
        file_obj = io.BytesIO(file_content.encode('utf-8'))
        file_obj.name = f"chunk_{chunk_id}.txt"
        
        # Upload to OpenAI
        try:
            file_response = self.client.files.create(
                file=file_obj,
                purpose="assistants"
            )
            
            # Add to vector store
            self.client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=file_response.id
            )
            
            return file_response.id
            
        except Exception as e:
            logger.error(f"Failed to add chunk to OpenAI Vector Store: {e}")
            raise
    
    async def add_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """Add multiple chunks for a document."""
        if not chunks:
            return []
        
        # Combine chunks into a single document for OpenAI Vector Store
        combined_content = []
        for i, chunk in enumerate(chunks):
            combined_content.append(f"## Chunk {i+1}")
            combined_content.append(chunk['text'])
            combined_content.append("")
        
        document_content = "\n".join(combined_content)
        
        # Create file
        import io
        file_content = f"# Document: {doc_id}\n\n{document_content}"
        file_obj = io.BytesIO(file_content.encode('utf-8'))
        file_obj.name = f"doc_{doc_id}.txt"
        
        try:
            # Upload file to OpenAI
            file_response = self.client.files.create(
                file=file_obj,
                purpose="assistants"
            )
            
            # Add to vector store
            self.client.vector_stores.files.create(
                vector_store_id=self.vector_store_id,
                file_id=file_response.id
            )
            
            logger.info(f"Added document {doc_id} to OpenAI Vector Store as file {file_response.id}")
            return [file_response.id]  # Return single file ID for all chunks
            
        except Exception as e:
            logger.error(f"Failed to add document to OpenAI Vector Store: {e}")
            raise
    
    async def query(
        self, 
        query_text: str, 
        n_results: int = 5, 
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query OpenAI Vector Store."""
        
        # Use the direct search API
        search_url = f"https://api.openai.com/v1/vector_stores/{self.vector_store_id}/files/search"
        
        headers = {
            "Authorization": f"Bearer {self.client.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2"
        }
        
        payload = {
            "query": query_text,
            "limit": n_results
        }
        
        try:
            response = await self.http_client.post(
                search_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                search_results = response.json()
                return {
                    'documents': [result.get('content', '') for result in search_results.get('data', [])],
                    'metadatas': [result.get('metadata', {}) for result in search_results.get('data', [])],
                    'distances': [1.0 - result.get('score', 0.0) for result in search_results.get('data', [])],
                    'ids': [result.get('file_id', '') for result in search_results.get('data', [])]
                }
            else:
                logger.error(f"OpenAI Vector Store search failed: {response.status_code} {response.text}")
                return {'documents': [], 'metadatas': [], 'distances': [], 'ids': []}
                
        except Exception as e:
            logger.error(f"Vector store query failed: {e}")
            return {'documents': [], 'metadatas': [], 'distances': [], 'ids': []}
    
    async def delete(self, chunk_id: str) -> bool:
        """Delete a file from OpenAI Vector Store."""
        try:
            # Remove from vector store
            self.client.vector_stores.files.delete(
                vector_store_id=self.vector_store_id,
                file_id=chunk_id
            )
            
            # Delete the file itself
            self.client.files.delete(chunk_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete from OpenAI Vector Store: {e}")
            return False
    
    async def count(self) -> int:
        """Get file count in OpenAI Vector Store."""
        try:
            vector_store = self.client.vector_stores.retrieve(self.vector_store_id)
            return vector_store.file_counts.total
        except Exception as e:
            logger.error(f"Failed to get OpenAI Vector Store count: {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI Vector Store health."""
        try:
            vector_store = self.client.vector_stores.retrieve(self.vector_store_id)
            return {
                'status': 'healthy',
                'backend': 'openai',
                'vector_store_id': self.vector_store_id,
                'file_count': vector_store.file_counts.total,
                'store_status': vector_store.status
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'backend': 'openai',
                'error': str(e)
            }