"""Base vector backend interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class VectorBackend(ABC):
    """Abstract base class for vector storage backends."""
    
    @abstractmethod
    async def add(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Add a document chunk to the vector store.
        
        Args:
            text: The text content to embed and store
            metadata: Associated metadata for the chunk
            
        Returns:
            The unique ID of the stored chunk
        """
        pass
    
    @abstractmethod
    async def add_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple chunks for a document.
        
        Args:
            doc_id: Document identifier
            chunks: List of chunk dictionaries with 'text' and 'metadata'
            
        Returns:
            List of chunk IDs
        """
        pass
    
    @abstractmethod
    async def query(
        self, 
        query_text: str, 
        n_results: int = 5, 
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query the vector store for similar documents.
        
        Args:
            query_text: Text to search for
            n_results: Number of results to return
            where: Optional metadata filters
            
        Returns:
            Search results with documents and scores
        """
        pass
    
    @abstractmethod
    async def delete(self, chunk_id: str) -> bool:
        """
        Delete a chunk from the vector store.
        
        Args:
            chunk_id: ID of the chunk to delete
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """
        Get the total number of chunks in the vector store.
        
        Returns:
            Total count of stored chunks
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the vector backend.
        
        Returns:
            Health status information
        """
        pass