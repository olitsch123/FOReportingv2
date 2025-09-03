"""Vector storage for PE documents with OpenAI Vector Store support."""
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import openai
from app.config import settings

class VectorStore:
    """Vector storage supporting both Chroma and OpenAI Vector Store."""
    
    def __init__(self):
        self.backend = settings.get('VECTOR_BACKEND', 'openai').lower()
        self.client = None
        self.vector_store_id = None
        
        if self.backend == 'openai':
            self._init_openai()
        elif self.backend == 'chroma':
            self._init_chroma()
        else:
            raise ValueError(f"Unsupported vector backend: {self.backend}")
    
    def _init_openai(self):
        """Initialize OpenAI Vector Store."""
        api_key = settings.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI vector backend")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.vector_store_id = settings.get('OPENAI_VECTOR_STORE_ID')
        
        if not self.vector_store_id:
            raise ValueError("OPENAI_VECTOR_STORE_ID required for OpenAI vector backend")
    
    def _init_chroma(self):
        """Initialize Chroma."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            chroma_dir = settings.get('CHROMA_DIR', './data/chroma')
            Path(chroma_dir).mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="pe_docs",
                metadata={"description": "PE document chunks"}
            )
        except ImportError:
            raise ValueError("chromadb package required for chroma backend")
    
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Add document chunks to vector store.
        Each chunk should have: doc_id, page_no, text, metadata.
        """
        if not chunks:
            return True
        
        try:
            if self.backend == 'openai':
                return self._add_chunks_openai(chunks)
            elif self.backend == 'chroma':
                return self._add_chunks_chroma(chunks)
        except Exception as e:
            print(f"Error adding chunks to vector store: {e}")
            return False
        
        return False
    
    def _add_chunks_openai(self, chunks: List[Dict[str, Any]]) -> bool:
        """Add chunks to OpenAI Vector Store."""
        # Create file objects for OpenAI
        files_to_upload = []
        
        for chunk in chunks:
            # Create temporary text content
            content = f"Document: {chunk.get('doc_id', 'unknown')}\\n"
            content += f"Page: {chunk.get('page_no', 1)}\\n"
            content += f"Content: {chunk.get('text', '')}"
            
            # Create file-like object
            file_obj = {
                'content': content,
                'metadata': {
                    'doc_id': chunk.get('doc_id'),
                    'doc_type': chunk.get('doc_type'),
                    'fund_id': chunk.get('fund_id'),
                    'investor_id': chunk.get('investor_id'),
                    'period_end': chunk.get('period_end'),
                    'page_no': str(chunk.get('page_no', 1))
                }
            }
            files_to_upload.append(file_obj)
        
        # Upload to OpenAI Vector Store
        for file_data in files_to_upload:
            try:
                # Create a temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
                    tmp_file.write(file_data['content'])
                    tmp_file_path = tmp_file.name
                
                # Upload file
                with open(tmp_file_path, 'rb') as f:
                    file_obj = self.client.files.create(
                        file=f,
                        purpose='assistants'
                    )
                
                # Add to vector store
                self.client.beta.vector_stores.files.create(
                    vector_store_id=self.vector_store_id,
                    file_id=file_obj.id
                )
                
                # Clean up temp file
                os.unlink(tmp_file_path)
                
            except Exception as e:
                print(f"Error uploading chunk to OpenAI: {e}")
                continue
        
        return True
    
    def _add_chunks_chroma(self, chunks: List[Dict[str, Any]]) -> bool:
        """Add chunks to Chroma."""
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{chunk.get('doc_id', 'unknown')}_{chunk.get('page_no', 1)}_{i}"
            
            documents.append(chunk.get('text', ''))
            metadatas.append({
                'doc_id': chunk.get('doc_id'),
                'doc_type': chunk.get('doc_type'),
                'fund_id': chunk.get('fund_id'),
                'investor_id': chunk.get('investor_id'),
                'period_end': chunk.get('period_end'),
                'page_no': chunk.get('page_no', 1)
            })
            ids.append(chunk_id)
        
        # Add to collection
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return True
    
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search vector store for relevant chunks.
        """
        try:
            if self.backend == 'openai':
                return self._search_openai(query, filters, top_k)
            elif self.backend == 'chroma':
                return self._search_chroma(query, filters, top_k)
        except Exception as e:
            print(f"Error searching vector store: {e}")
            return []
        
        return []
    
    def _search_openai(self, query: str, filters: Optional[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Search OpenAI Vector Store."""
        # Note: OpenAI Vector Store search is typically done through assistants
        # For direct search, we'd need to implement embedding-based search
        # This is a simplified version
        
        results = []
        
        try:
            # Get embeddings for query
            embedding_response = self.client.embeddings.create(
                model=settings.get('OPENAI_EMBED_MODEL', 'text-embedding-3-large'),
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            
            # For now, return empty results as OpenAI Vector Store 
            # direct search requires more complex implementation
            # In practice, this would be used with assistants API
            
        except Exception as e:
            print(f"OpenAI search error: {e}")
        
        return results
    
    def _search_chroma(self, query: str, filters: Optional[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Search Chroma collection."""
        where_clause = {}
        if filters:
            for key, value in filters.items():
                if value is not None:
                    where_clause[key] = value
        
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_clause if where_clause else None
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                result = {
                    'text': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {},
                    'distance': results['distances'][0][i] if results['distances'] and results['distances'][0] else 0,
                    'id': results['ids'][0][i] if results['ids'] and results['ids'][0] else f"chunk_{i}"
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def delete_document_chunks(self, doc_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            if self.backend == 'chroma':
                # Get all chunk IDs for this document
                results = self.collection.get(where={"doc_id": doc_id})
                if results['ids']:
                    self.collection.delete(ids=results['ids'])
            elif self.backend == 'openai':
                # OpenAI Vector Store deletion would require file management
                # This is a simplified placeholder
                pass
            
            return True
        except Exception as e:
            print(f"Error deleting document chunks: {e}")
            return False

# Global vector store instance
def get_vector_store() -> VectorStore:
    """Get vector store instance."""
    return VectorStore()