"""Document processing service."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database.connection import get_db_session
from app.database.models import (
    Document, DocumentType, ProcessingStatus, 
    Investor, Fund, FinancialData, DocumentEmbedding
)
from app.processors.processor_factory import ProcessorFactory
from app.processors.base import ProcessedDocument
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document processing and management."""
    
    def __init__(self):
        """Initialize the document service."""
        self.processor_factory = ProcessorFactory()
        self.vector_service = VectorService()
    
    async def process_document(self, file_path: str, investor_code: str) -> Optional[Document]:
        """Process a document and store it in the database."""
        try:
            logger.info(f"Processing document: {file_path}")
            
            # Get or create investor
            with get_db_session() as db:
                investor = self._get_or_create_investor(db, investor_code)
                if not investor:
                    logger.error(f"Could not create investor: {investor_code}")
                    return None
            
            # Get appropriate processor
            processor = self.processor_factory.get_processor(file_path)
            if not processor:
                logger.error(f"No processor available for file: {file_path}")
                return None
            
            # Check if document already exists
            with get_db_session() as db:
                existing_doc = db.query(Document).filter(
                    Document.file_path == str(Path(file_path).absolute())
                ).first()
                
                if existing_doc:
                    # Update processing status
                    existing_doc.processing_status = ProcessingStatus.PROCESSING
                    db.commit()
                    document_id = existing_doc.id
                else:
                    # Create new document record
                    document = Document(
                        filename=Path(file_path).name,
                        file_path=str(Path(file_path).absolute()),
                        investor_id=investor.id,
                        processing_status=ProcessingStatus.PROCESSING
                    )
                    db.add(document)
                    db.commit()
                    db.refresh(document)
                    document_id = document.id
            
            # Process the document
            try:
                processed_doc = processor.process(file_path)
                
                # Update document with processed data
                with get_db_session() as db:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if not document:
                        logger.error(f"Document not found: {document_id}")
                        return None
                    
                    # Update document fields
                    document.file_size = processed_doc.file_size
                    document.file_hash = processed_doc.file_hash
                    document.mime_type = processed_doc.mime_type
                    document.document_type = processed_doc.document_type.value
                    document.confidence_score = processed_doc.confidence_score
                    document.raw_text = processed_doc.raw_text
                    document.structured_data = processed_doc.structured_data
                    document.summary = processed_doc.summary
                    document.processing_status = ProcessingStatus.COMPLETED
                    document.processed_at = datetime.utcnow()
                    
                    # Set reporting date if available
                    if processed_doc.reporting_date:
                        try:
                            document.reporting_date = datetime.fromisoformat(
                                processed_doc.reporting_date.replace('Z', '+00:00')
                            )
                        except ValueError:
                            pass
                    
                    # Try to match with fund
                    fund = self._match_fund(db, processed_doc.structured_data, investor.id)
                    if fund:
                        document.fund_id = fund.id
                    
                    db.commit()
                    db.refresh(document)
                
                # Extract and store financial data
                await self._extract_and_store_financial_data(document_id, processed_doc)
                
                # Create embeddings for vector search
                await self._create_document_embeddings(document_id, processed_doc.raw_text)
                
                logger.info(f"Successfully processed document: {file_path}")
                return document
                
            except Exception as e:
                # Update document with error status
                with get_db_session() as db:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if document:
                        document.processing_status = ProcessingStatus.FAILED
                        document.processing_error = str(e)
                        db.commit()
                
                logger.error(f"Error processing document {file_path}: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error processing document {file_path}: {str(e)}")
            return None
    
    async def get_document_by_path(self, file_path: str) -> Optional[Document]:
        """Get document by file path."""
        try:
            with get_db_session() as db:
                return db.query(Document).filter(
                    Document.file_path == str(Path(file_path).absolute())
                ).first()
        except Exception as e:
            logger.error(f"Error getting document by path {file_path}: {str(e)}")
            return None
    
    async def get_documents(
        self, 
        investor_code: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """Get documents with optional filtering."""
        try:
            with get_db_session() as db:
                query = db.query(Document)
                
                if investor_code:
                    query = query.join(Investor).filter(Investor.code == investor_code)
                
                if document_type:
                    query = query.filter(Document.document_type == document_type.value)
                
                return query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
                
        except Exception as e:
            logger.error(f"Error getting documents: {str(e)}")
            return []
    
    def _get_or_create_investor(self, db: Session, investor_code: str) -> Optional[Investor]:
        """Get or create investor by code."""
        try:
            investor = db.query(Investor).filter(Investor.code == investor_code).first()
            
            if not investor:
                # Create new investor
                investor_data = self._get_investor_data(investor_code)
                if not investor_data:
                    return None
                
                investor = Investor(**investor_data)
                db.add(investor)
                db.commit()
                db.refresh(investor)
            
            return investor
            
        except Exception as e:
            logger.error(f"Error getting/creating investor {investor_code}: {str(e)}")
            db.rollback()
            return None
    
    def _get_investor_data(self, investor_code: str) -> Optional[Dict[str, Any]]:
        """Get investor data by code."""
        from app.config import INVESTOR_FOLDERS
        
        investor_configs = {
            "brainweb": {
                "name": "BrainWeb Investment GmbH",
                "code": "brainweb",
                "description": "BrainWeb Investment GmbH - Private Equity and Venture Capital",
                "folder_path": INVESTOR_FOLDERS.get("brainweb", "")
            },
            "pecunalta": {
                "name": "pecunalta GmbH",
                "code": "pecunalta", 
                "description": "pecunalta GmbH - Investment Management",
                "folder_path": INVESTOR_FOLDERS.get("pecunalta", "")
            }
        }
        
        return investor_configs.get(investor_code)
    
    def _match_fund(self, db: Session, structured_data: Dict[str, Any], investor_id: str) -> Optional[Fund]:
        """Try to match document with existing fund or create new one."""
        try:
            fund_info = structured_data.get('fund_information', {})
            if not fund_info:
                return None
            
            fund_name = fund_info.get('fund_name')
            fund_code = fund_info.get('fund_code')
            
            if not fund_name and not fund_code:
                return None
            
            # Try to find existing fund
            query = db.query(Fund).filter(Fund.investor_id == investor_id)
            
            if fund_code:
                fund = query.filter(Fund.code == fund_code).first()
                if fund:
                    return fund
            
            if fund_name:
                fund = query.filter(Fund.name.ilike(f"%{fund_name}%")).first()
                if fund:
                    return fund
            
            # Create new fund if not found
            if fund_name or fund_code:
                fund = Fund(
                    name=fund_name or fund_code,
                    code=fund_code or fund_name[:20],  # Truncate if needed
                    asset_class=fund_info.get('asset_class', 'other'),
                    vintage_year=fund_info.get('vintage_year'),
                    investor_id=investor_id
                )
                db.add(fund)
                db.commit()
                db.refresh(fund)
                return fund
            
            return None
            
        except Exception as e:
            logger.error(f"Error matching fund: {str(e)}")
            return None
    
    async def _extract_and_store_financial_data(
        self, 
        document_id: str, 
        processed_doc: ProcessedDocument
    ):
        """Extract and store financial data from processed document."""
        try:
            structured_data = processed_doc.structured_data
            financial_metrics = structured_data.get('financial_metrics', {})
            
            if not financial_metrics:
                return
            
            with get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document or not document.fund_id:
                    return
                
                # Determine reporting date
                reporting_date = None
                if document.reporting_date:
                    reporting_date = document.reporting_date
                elif structured_data.get('reporting_date'):
                    try:
                        reporting_date = datetime.fromisoformat(
                            structured_data['reporting_date'].replace('Z', '+00:00')
                        )
                    except ValueError:
                        pass
                
                if not reporting_date:
                    reporting_date = datetime.utcnow()
                
                # Determine period type
                period_info = structured_data.get('period_information', {})
                period_type = period_info.get('period_type', 'unknown')
                
                # Check if financial data already exists
                existing_data = db.query(FinancialData).filter(
                    and_(
                        FinancialData.fund_id == document.fund_id,
                        FinancialData.reporting_date == reporting_date,
                        FinancialData.period_type == period_type
                    )
                ).first()
                
                if existing_data:
                    # Update existing data
                    for key, value in financial_metrics.items():
                        if hasattr(existing_data, key) and value is not None:
                            setattr(existing_data, key, value)
                    existing_data.document_id = document_id
                    existing_data.updated_at = datetime.utcnow()
                else:
                    # Create new financial data
                    financial_data = FinancialData(
                        document_id=document_id,
                        fund_id=document.fund_id,
                        reporting_date=reporting_date,
                        period_type=period_type,
                        **{k: v for k, v in financial_metrics.items() if v is not None}
                    )
                    db.add(financial_data)
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error storing financial data for document {document_id}: {str(e)}")
    
    async def _create_document_embeddings(self, document_id: str, text: str):
        """Create embeddings for document text."""
        try:
            # Split text into chunks
            chunks = self._split_text_into_chunks(text)
            
            with get_db_session() as db:
                # Remove existing embeddings
                db.query(DocumentEmbedding).filter(
                    DocumentEmbedding.document_id == document_id
                ).delete()
                
                # Create new embeddings
                for i, chunk in enumerate(chunks):
                    # Create embedding in vector store
                    embedding_id = await self.vector_service.add_document(
                        document_id=str(document_id),
                        text=chunk,
                        metadata={
                            'document_id': str(document_id),
                            'chunk_index': i
                        }
                    )
                    
                    if embedding_id:
                        # Store embedding metadata in database
                        doc_embedding = DocumentEmbedding(
                            document_id=document_id,
                            chunk_index=i,
                            chunk_text=chunk,
                            embedding_id=embedding_id
                        )
                        db.add(doc_embedding)
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error creating embeddings for document {document_id}: {str(e)}")
    
    def _split_text_into_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + chunk_size // 2, end - 200), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(text) else end
        
        return chunks