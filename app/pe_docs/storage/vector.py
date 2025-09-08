"""Vector storage for PE documents with backend switching."""

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import httpx
import openai
from chromadb.config import Settings
from structlog import get_logger

from app.config import load_settings

logger = get_logger()
settings = load_settings()


class PEVectorStore:
    """
    Vector store for PE documents supporting multiple backends.
    
    Backends:
    - chroma: Local ChromaDB instance
    - openai: OpenAI Vector Store API
    """
    
    def __init__(self):
        """Initialize vector store based on configuration."""
        self.backend = settings.get("vector_backend", "openai")
        self.collection_name = "pe_docs"
        
        if self.backend == "chroma":
            self._init_chroma()
        elif self.backend == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unknown vector backend: {self.backend}")
        
        logger.info(
            "pe_vector_store_initialized",
            backend=self.backend,
            collection=self.collection_name
        )
    
    def _init_chroma(self):
        """Initialize ChromaDB backend."""
        try:
            chroma_dir = os.getenv("CHROMA_DIR", "./data/chroma")
            self.chroma_client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(self.collection_name)
            except:
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "PE document embeddings"}
                )
            
            # Initialize OpenAI for embeddings
            self.openai_client = openai.OpenAI(
                api_key=settings.get("OPENAI_API_KEY")
            )
            self.embedding_model = settings.get("openai", {}).get(
                "embedding_model", "text-embedding-3-large"
            )
            
        except Exception as e:
            logger.error(
                "chroma_init_failed",
                error=str(e)
            )
            raise
    
    def _init_openai(self):
        """Initialize OpenAI Vector Store backend."""
        try:
            self.openai_client = openai.OpenAI(
                api_key=settings.get("OPENAI_API_KEY")
            )
            self.vector_store_id = os.getenv("OPENAI_VECTOR_STORE_ID")
            
            if not self.vector_store_id:
                raise ValueError("OPENAI_VECTOR_STORE_ID not set in environment")
            
            # Verify vector store exists
            try:
                self.vector_store = self.openai_client.vector_stores.retrieve(
                    self.vector_store_id
                )
            except Exception as e:
                logger.error(
                    "openai_vector_store_not_found",
                    vector_store_id=self.vector_store_id,
                    error=str(e)
                )
                raise ValueError(f"Vector store {self.vector_store_id} not found")
            
            self.embedding_model = settings.get("openai", {}).get(
                "embedding_model", "text-embedding-3-large"
            )
            
        except Exception as e:
            logger.error(
                "openai_init_failed",
                error=str(e)
            )
            raise
    
    async def add_chunks(self, 
                        doc_id: str,
                        chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Add document chunks to vector store.
        
        Args:
            doc_id: Document ID
            chunks: List of chunks with 'text', 'page_no', 'metadata'
            
        Returns:
            List of chunk IDs
        """
        if self.backend == "chroma":
            return await self._add_chunks_chroma(doc_id, chunks)
        else:
            return await self._add_chunks_openai(doc_id, chunks)
    
    async def _add_chunks_chroma(self, 
                                doc_id: str,
                                chunks: List[Dict[str, Any]]) -> List[str]:
        """Add chunks to ChromaDB."""
        chunk_ids = []
        
        for chunk in chunks:
            # Generate embedding
            embedding = await self._create_embedding(chunk['text'])
            if not embedding:
                continue
            
            # Create chunk ID
            chunk_id = str(uuid.uuid4())
            
            # Prepare metadata
            metadata = {
                'doc_id': doc_id,
                'page_no': chunk.get('page_no', 0),
                'doc_type': chunk.get('doc_type', 'unknown'),
                'fund_id': chunk.get('fund_id', ''),
                'investor_id': chunk.get('investor_id', ''),
                'period_end': chunk.get('period_end', ''),
                'chunk_index': chunk.get('index', 0),
                **chunk.get('metadata', {})
            }
            
            # Add to collection
            self.collection.add(
                embeddings=[embedding],
                documents=[chunk['text']],
                metadatas=[metadata],
                ids=[chunk_id]
            )
            
            chunk_ids.append(chunk_id)
        
        logger.info(
            "chunks_added_to_chroma",
            doc_id=doc_id,
            chunk_count=len(chunk_ids)
        )
        
        return chunk_ids
    
    async def _add_chunks_openai(self, 
                                doc_id: str,
                                chunks: List[Dict[str, Any]]) -> List[str]:
        """Add chunks to OpenAI Vector Store."""
        chunk_ids = []
        
        # Prepare batch of files
        files_to_upload = []
        
        for i, chunk in enumerate(chunks):
            # Create a file-like object with chunk text
            chunk_content = f"""Document: {doc_id}
Page: {chunk.get('page_no', 0)}
Type: {chunk.get('doc_type', 'unknown')}
Fund: {chunk.get('fund_id', '')}
Investor: {chunk.get('investor_id', '')}
Period: {chunk.get('period_end', '')}

{chunk['text']}"""
            
            # Upload file to OpenAI
            file_response = self.openai_client.files.create(
                file=chunk_content.encode('utf-8'),
                purpose="assistants"
            )
            
            files_to_upload.append(file_response.id)
            chunk_ids.append(file_response.id)
        
        # Add files to vector store
        if files_to_upload:
            batch_response = self.openai_client.vector_stores.file_batches.create(
                vector_store_id=self.vector_store_id,
                file_ids=files_to_upload
            )
            
            logger.info(
                "chunks_added_to_openai",
                doc_id=doc_id,
                chunk_count=len(chunk_ids),
                batch_id=batch_response.id
            )
        
        return chunk_ids
    
    async def search(self, 
                    query: str,
                    top_k: int = 5,
                    filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Search vector store with query.
        
        Args:
            query: Search query text
            top_k: Number of results
            filters: Metadata filters
            
        Returns:
            List of search results with metadata and scores
        """
        if self.backend == "chroma":
            return await self._search_chroma(query, top_k, filters)
        else:
            return await self._search_openai(query, top_k, filters)
    
    async def _search_chroma(self, 
                           query: str,
                           top_k: int,
                           filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Search ChromaDB."""
        # Create query embedding
        query_embedding = await self._create_embedding(query)
        if not query_embedding:
            return []
        
        # Build where clause from filters
        where = {}
        if filters:
            for key, value in filters.items():
                if value is not None and value != '':
                    where[key] = value
        
        # Search collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where if where else None,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': 1 - results['distances'][0][i],  # Convert distance to similarity
                    'backend': 'chroma'
                })
        
        return formatted_results
    
    async def _search_openai(self, 
                           query: str,
                           top_k: int,
                           filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Search OpenAI Vector Store using direct API."""
        try:
            # Use httpx to call the vector store search API directly
            endpoint = f"https://api.openai.com/v1/vector_stores/{self.vector_store_id}/search"
            
            headers = {
                'Authorization': f'Bearer {settings.get("OPENAI_API_KEY")}',
                'Content-Type': 'application/json',
                'OpenAI-Beta': 'assistants=v2'
            }
            
            # Build search payload
            payload = {
                "query": query,
                "max_num_results": top_k,
                "rewrite_query": True
            }
            
            # Add filters if provided
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    if value is not None and value != '':
                        filter_conditions.append({
                            "key": key,
                            "type": "eq",
                            "value": value
                        })
                
                if filter_conditions:
                    if len(filter_conditions) > 1:
                        payload["filters"] = {
                            "type": "and",
                            "filters": filter_conditions
                        }
                    else:
                        payload["filters"] = filter_conditions[0]
            
            # Make the API request
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(
                        "vector_store_search_failed",
                        status_code=response.status_code,
                        response=response.text
                    )
                    return []
                
                result = response.json()
                
            # Format results
            formatted_results = []
            for item in result.get('data', []):
                # Extract text content
                text_content = ""
                for content in item.get('content', []):
                    if content.get('type') == 'text':
                        text_content = content.get('text', '')
                        break
                
                formatted_results.append({
                    'id': item.get('file_id'),
                    'text': text_content,
                    'metadata': {
                        'filename': item.get('filename'),
                        'attributes': item.get('attributes', {}),
                        'file_id': item.get('file_id')
                    },
                    'score': float(item.get('score', 0.0)),
                    'backend': 'openai'
                })
            
            logger.info(
                "vector_store_search_success",
                query=query[:50],
                result_count=len(formatted_results)
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(
                "vector_store_search_error",
                error=str(e),
                query=query[:50]
            )
            return []
    
    async def _create_embedding(self, text: str) -> Optional[List[float]]:
        """Create embedding using OpenAI."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(
                "embedding_creation_failed",
                error=str(e)
            )
            return None
    
    async def delete_document(self, doc_id: str) -> bool:
        """Delete all chunks for a document."""
        if self.backend == "chroma":
            return await self._delete_document_chroma(doc_id)
        else:
            return await self._delete_document_openai(doc_id)
    
    async def _delete_document_chroma(self, doc_id: str) -> bool:
        """Delete document from ChromaDB."""
        try:
            # Get all chunks for document
            results = self.collection.get(
                where={"doc_id": doc_id}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(
                    "document_deleted_from_chroma",
                    doc_id=doc_id,
                    chunk_count=len(results['ids'])
                )
            
            return True
            
        except Exception as e:
            logger.error(
                "document_deletion_failed",
                doc_id=doc_id,
                error=str(e)
            )
            return False
    
    async def _delete_document_openai(self, doc_id: str) -> bool:
        """Delete document from OpenAI Vector Store."""
        # OpenAI doesn't support selective deletion from vector stores
        # Would need to track file IDs separately
        logger.warning(
            "document_deletion_not_supported",
            backend="openai",
            doc_id=doc_id
        )
        return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        if self.backend == "chroma":
            count = self.collection.count()
            return {
                'backend': 'chroma',
                'collection': self.collection_name,
                'document_count': count,
                'status': 'connected'
            }
        else:
            # Get vector store info
            vs = self.openai_client.vector_stores.retrieve(
                self.vector_store_id
            )
            return {
                'backend': 'openai',
                'vector_store_id': self.vector_store_id,
                'file_count': vs.file_counts.total,
                'bytes': vs.usage_bytes,
                'status': vs.status
            }