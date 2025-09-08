"""Refactored document processing service with improved architecture."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.connection import get_db_session
from app.database.models import (
    Document,
    DocumentEmbedding,
    DocumentType,
    FinancialData,
    Fund,
    Investor,
    ProcessingStatus,
)
from app.pe_docs.extractors.multi_method import MultiMethodExtractor
from app.processors.base import ProcessedDocument
from app.processors.processor_factory import ProcessorFactory
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors."""
    pass


class DocumentService:
    """Refactored document processing service with clear separation of concerns."""
    
    def __init__(self):
        """Initialize the document service."""
        self.processor_factory = ProcessorFactory()
        self.vector_service = VectorService()
        self.pe_extractor = MultiMethodExtractor()
    
    async def process_document(self, file_path: str, investor_code: str) -> Optional[Document]:
        """
        Main document processing orchestrator - refactored into focused steps.
        
        This method now delegates to specialized methods for each processing step.
        """
        try:
            logger.info(f"Starting document processing: {file_path}")
            
            # Step 1: Validate and prepare
            investor = await self._validate_and_get_investor(investor_code)
            processor = self._get_document_processor(file_path)
            
            # Step 2: Create or get document record
            document = await self._create_or_get_document_record(file_path, investor.id)
            
            # Step 3: Process document content
            processed_doc = await self._process_document_content(processor, file_path)
            
            # Step 4: Update document with processed data
            document = await self._update_document_with_processed_data(document.id, processed_doc)
            
            # Step 5: Handle PE-specific extraction if applicable
            if self._is_pe_document(document.document_type):
                await self._handle_pe_extraction(document, processed_doc, file_path)
            
            # Step 6: Extract and store financial data
            await self._extract_and_store_financial_data(document.id, processed_doc)
            
            # Step 7: Create vector embeddings
            await self._create_document_embeddings(document.id, processed_doc.raw_text)
            
            # Step 8: Finalize processing
            await self._finalize_document_processing(document.id)
            
            logger.info(f"Successfully completed document processing: {file_path}")
            return document
            
        except DocumentProcessingError as e:
            await self._handle_processing_error(file_path, str(e))
            return None
        except Exception as e:
            await self._handle_unexpected_error(file_path, str(e))
            return None
    
    async def _validate_and_get_investor(self, investor_code: str) -> Investor:
        """Validate and get or create investor."""
        try:
            with get_db_session() as db:
                investor = self._get_or_create_investor(db, investor_code)
                if not investor:
                    raise DocumentProcessingError(f"Could not create investor: {investor_code}")
                return investor
        except Exception as e:
            raise DocumentProcessingError(f"Investor validation failed: {e}")
    
    def _get_document_processor(self, file_path: str):
        """Get appropriate document processor."""
        processor = self.processor_factory.get_processor(file_path)
        if not processor:
            raise DocumentProcessingError(f"No processor available for file: {file_path}")
        return processor
    
    async def _create_or_get_document_record(self, file_path: str, investor_id: str) -> Document:
        """Create new document record or get existing one."""
        try:
            with get_db_session() as db:
                absolute_path = str(Path(file_path).absolute())
                existing_doc = db.query(Document).filter(
                    Document.file_path == absolute_path
                ).first()
                
                if existing_doc:
                    # Update processing status
                    existing_doc.processing_status = ProcessingStatus.PROCESSING
                    db.commit()
                    db.refresh(existing_doc)
                    return existing_doc
                else:
                    # Create new document record
                    document = Document(
                        filename=Path(file_path).name,
                        file_path=absolute_path,
                        investor_id=investor_id,
                        processing_status=ProcessingStatus.PROCESSING
                    )
                    db.add(document)
                    db.commit()
                    db.refresh(document)
                    return document
                    
        except Exception as e:
            raise DocumentProcessingError(f"Failed to create document record: {e}")
    
    async def _process_document_content(self, processor, file_path: str) -> ProcessedDocument:
        """Process document content using appropriate processor."""
        try:
            logger.debug(f"Processing document content with {type(processor).__name__}")
            processed_doc = processor.process(file_path)
            
            if not processed_doc:
                raise DocumentProcessingError("Processor returned no result")
            
            return processed_doc
            
        except Exception as e:
            raise DocumentProcessingError(f"Content processing failed: {e}")
    
    async def _update_document_with_processed_data(
        self, 
        document_id: str, 
        processed_doc: ProcessedDocument
    ) -> Document:
        """Update document record with processed data."""
        try:
            with get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document:
                    raise DocumentProcessingError(f"Document not found: {document_id}")
                
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
                        logger.warning(f"Could not parse reporting date: {processed_doc.reporting_date}")
                
                # Try to match with fund
                fund = self._match_fund(db, processed_doc.structured_data, document.investor_id)
                if fund:
                    document.fund_id = fund.id
                
                db.commit()
                db.refresh(document)
                return document
                
        except Exception as e:
            raise DocumentProcessingError(f"Failed to update document data: {e}")
    
    def _is_pe_document(self, document_type: str) -> bool:
        """Check if document type requires PE-specific processing."""
        pe_document_types = [
            'quarterly_report', 
            'capital_account_statement',
            'capital_call_notice', 
            'distribution_notice'
        ]
        return document_type in pe_document_types
    
    async def _handle_pe_extraction(
        self, 
        document: Document, 
        processed_doc: ProcessedDocument, 
        file_path: str
    ):
        """Handle PE-specific extraction for relevant document types."""
        try:
            logger.debug(f"Starting PE extraction for {document.document_type}")
            
            # Get tables from processed doc if available
            tables = processed_doc.structured_data.get('tables', []) if processed_doc.structured_data else []
            
            # Prepare metadata
            doc_metadata = {
                'doc_id': str(document.id),
                'doc_type': document.document_type,
                'filename': document.filename,
                'fund_id': str(document.fund_id) if document.fund_id else None,
                'investor_id': str(document.investor_id),
                'period_end': document.reporting_date,
                'as_of_date': document.reporting_date
            }
            
            # Run PE extraction
            pe_result = await self.pe_extractor.process_document(
                file_path=file_path,
                text=processed_doc.raw_text,
                tables=tables,
                doc_metadata=doc_metadata
            )
            
            # Update document with PE extraction results
            if pe_result['status'] == 'success':
                await self._update_document_with_pe_results(document.id, pe_result)
                logger.info(
                    f"PE extraction completed for {file_path}. "
                    f"Confidence: {pe_result['overall_confidence']:.2f}, "
                    f"Requires review: {pe_result['requires_review']}"
                )
            else:
                logger.warning(f"PE extraction returned non-success status: {pe_result.get('status')}")
                
        except Exception as e:
            logger.error(f"PE extraction failed for {file_path}: {e}")
            # Continue with regular processing even if PE extraction fails
    
    async def _update_document_with_pe_results(self, document_id: str, pe_result: Dict[str, Any]):
        """Update document with PE extraction results."""
        try:
            with get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.structured_data = {
                        **(document.structured_data or {}),
                        'pe_extraction': pe_result['extracted_data'],
                        'validation': pe_result['validation'],
                        'extraction_confidence': pe_result['overall_confidence']
                    }
                    db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to update document with PE results: {e}")
            raise DocumentProcessingError(f"PE results update failed: {e}")
    
    async def _finalize_document_processing(self, document_id: str):
        """Finalize document processing status."""
        try:
            with get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if document:
                    document.processing_status = ProcessingStatus.COMPLETED
                    document.processed_at = datetime.utcnow()
                    db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to finalize document processing: {e}")
    
    async def _handle_processing_error(self, file_path: str, error_message: str):
        """Handle processing errors with proper status updates."""
        try:
            logger.error(f"Processing error for {file_path}: {error_message}")
            # Additional error handling logic could go here
            # e.g., update document status, send notifications, etc.
        except Exception as e:
            logger.error(f"Error handling failed: {e}")
    
    async def _handle_unexpected_error(self, file_path: str, error_message: str):
        """Handle unexpected errors during processing."""
        try:
            logger.error(f"Unexpected error processing {file_path}: {error_message}")
            # Additional error handling logic could go here
        except Exception as e:
            logger.error(f"Unexpected error handling failed: {e}")
    
    # Keep all the existing helper methods unchanged
    def _get_or_create_investor(self, db: Session, investor_code: str) -> Optional[Investor]:
        """Get or create investor - unchanged from original."""
        try:
            investor = db.query(Investor).filter(Investor.code == investor_code).first()
            
            if not investor:
                # Create new investor with basic info
                investor_info = self._get_investor_info(investor_code)
                investor = Investor(
                    name=investor_info['name'],
                    code=investor_code,
                    description=investor_info['description'],
                    folder_path=investor_info['folder_path']
                )
                db.add(investor)
                db.commit()
                db.refresh(investor)
                logger.info(f"Created new investor: {investor_code}")
            
            return investor
            
        except Exception as e:
            logger.error(f"Error getting/creating investor {investor_code}: {str(e)}")
            return None
    
    def _get_investor_info(self, investor_code: str) -> Dict[str, str]:
        """Get investor information based on code."""
        investor_mappings = {
            'brainweb': {
                'name': 'BrainWeb Investment GmbH',
                'description': 'BrainWeb Investment GmbH - Private Equity and Venture Capital',
                'folder_path': '/path/to/brainweb'
            },
            'pecunalta': {
                'name': 'pecunalta GmbH',
                'description': 'pecunalta GmbH - Investment Management',
                'folder_path': '/path/to/pecunalta'
            }
        }
        
        return investor_mappings.get(investor_code, {
            'name': f'Unknown Investor ({investor_code})',
            'description': f'Investor {investor_code}',
            'folder_path': f'/unknown/{investor_code}'
        })
    
    def _match_fund(self, db: Session, structured_data: Optional[Dict], investor_id: str) -> Optional[Fund]:
        """Match document to fund based on structured data."""
        if not structured_data:
            return None
        
        try:
            # Try to extract fund name from structured data
            fund_name = None
            
            # Check various possible fund name fields
            fund_name_fields = ['fund_name', 'fund', 'portfolio_name', 'investment_name']
            for field in fund_name_fields:
                if field in structured_data and structured_data[field]:
                    fund_name = structured_data[field]
                    break
            
            if fund_name:
                # Try to find existing fund
                fund = db.query(Fund).filter(
                    Fund.investor_id == investor_id,
                    Fund.name.ilike(f"%{fund_name}%")
                ).first()
                
                if fund:
                    return fund
                
                # Create new fund if not found
                fund = Fund(
                    name=fund_name,
                    code=fund_name.replace(' ', '_').upper()[:50],
                    asset_class='private_equity',  # Default for PE documents
                    investor_id=investor_id,
                    currency='EUR'  # Default currency
                )
                db.add(fund)
                db.commit()
                db.refresh(fund)
                logger.info(f"Created new fund: {fund_name}")
                return fund
            
        except Exception as e:
            logger.error(f"Error matching fund: {str(e)}")
        
        return None
    
    async def _extract_and_store_financial_data(self, document_id: str, processed_doc: ProcessedDocument):
        """Extract and store financial data from processed document."""
        try:
            if not processed_doc.structured_data:
                return
            
            # Extract financial metrics
            financial_data = self._extract_financial_metrics(processed_doc.structured_data)
            
            if financial_data:
                with get_db_session() as db:
                    document = db.query(Document).filter(Document.id == document_id).first()
                    if document and document.fund_id:
                        # Create financial data record
                        fin_data = FinancialData(
                            fund_id=document.fund_id,
                            document_id=document.id,
                            reporting_date=document.reporting_date or datetime.utcnow().date(),
                            period_type='quarterly',  # Default
                            **financial_data
                        )
                        db.add(fin_data)
                        db.commit()
                        logger.info(f"Stored financial data for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error extracting financial data: {e}")
    
    def _extract_financial_metrics(self, structured_data: Dict) -> Optional[Dict]:
        """Extract financial metrics from structured data."""
        try:
            metrics = {}
            
            # Extract common financial fields
            field_mappings = {
                'nav': ['nav', 'net_asset_value', 'ending_balance'],
                'total_value': ['total_value', 'portfolio_value'],
                'irr': ['irr', 'internal_rate_of_return'],
                'moic': ['moic', 'multiple_on_invested_capital'],
                'committed_capital': ['total_commitment', 'committed_capital'],
                'drawn_capital': ['drawn_commitment', 'called_capital'],
                'distributed_capital': ['total_distributions', 'distributions_itd']
            }
            
            for metric, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in structured_data and structured_data[field] is not None:
                        try:
                            metrics[metric] = float(structured_data[field])
                            break
                        except (ValueError, TypeError):
                            continue
            
            # Set currency if available
            if 'currency' in structured_data:
                metrics['currency'] = structured_data['currency']
            else:
                metrics['currency'] = 'EUR'  # Default
            
            return metrics if metrics else None
            
        except Exception as e:
            logger.error(f"Error extracting financial metrics: {e}")
            return None
    
    async def _create_document_embeddings(self, document_id: str, raw_text: str):
        """Create vector embeddings for document."""
        try:
            if not raw_text or len(raw_text.strip()) < 100:
                logger.debug(f"Skipping embeddings for document {document_id} - insufficient text")
                return
            
            # Create embeddings using vector service
            embedding_result = await self.vector_service.create_document_embeddings(
                document_id=document_id,
                text=raw_text
            )
            
            if embedding_result:
                logger.info(f"Created embeddings for document {document_id}")
            else:
                logger.warning(f"Failed to create embeddings for document {document_id}")
                
        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
    
    # Additional methods from the original service would be included here...
    # (keeping the rest of the existing methods unchanged)
    
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