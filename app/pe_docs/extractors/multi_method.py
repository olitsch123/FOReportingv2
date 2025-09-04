"""Multi-method extraction orchestrator for PE documents."""

import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import uuid

from .base import BaseExtractor, ExtractionResult, ExtractionMethod
from .capital_account import CapitalAccountExtractor
from app.pe_docs.classifiers import PEDocumentClassifier
from app.pe_docs.validation import DocumentValidator
from app.pe_docs.storage.orm import PEStorageORM

logger = logging.getLogger(__name__)


class MultiMethodExtractor:
    """Orchestrate multi-method extraction with validation and storage."""
    
    def __init__(self):
        """Initialize extractors and services."""
        self.extractors = {
            'capital_account_statement': CapitalAccountExtractor(),
            'quarterly_report': CapitalAccountExtractor(),  # QRs often have capital account data
            # Add more extractors as implemented:
            # 'performance_report': PerformanceMetricsExtractor(),
            # 'capital_call_notice': CashflowExtractor(),
            # 'distribution_notice': CashflowExtractor(),
        }
        
        self.classifier = PEDocumentClassifier()
        self.validator = DocumentValidator()
        self.storage = PEStorageORM()
    
    async def process_document(
        self,
        file_path: str,
        text: str,
        tables: List[Dict],
        doc_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process document with full extraction, validation, and storage pipeline."""
        
        try:
            # 1. Classify document if not already classified
            doc_type = doc_metadata.get('doc_type')
            if not doc_type:
                doc_type, confidence = self.classifier.classify(
                    text=text,
                    filename=doc_metadata.get('filename', ''),
                    first_pages=text[:5000]
                )
                doc_metadata['doc_type'] = doc_type
                doc_metadata['classification_confidence'] = confidence
            
            logger.info(f"Processing {doc_type} document: {file_path}")
            
            # 2. Get appropriate extractor
            extractor = self.extractors.get(doc_type)
            if not extractor:
                logger.warning(f"No extractor available for doc_type: {doc_type}")
                return {
                    'status': 'skipped',
                    'reason': f'No extractor for {doc_type}',
                    'doc_metadata': doc_metadata
                }
            
            # 3. Extract data using multiple methods
            extracted_data = await extractor.extract(text, tables, doc_type)
            
            # 4. Add document metadata
            extracted_data.update({
                'doc_id': doc_metadata.get('doc_id', str(uuid.uuid4())),
                'doc_type': doc_type,
                'file_path': file_path,
                'fund_id': doc_metadata.get('fund_id'),
                'investor_id': doc_metadata.get('investor_id'),
                'period_end': doc_metadata.get('period_end'),
                'as_of_date': doc_metadata.get('as_of_date'),
                'reporting_currency': doc_metadata.get('currency', 'USD')
            })
            
            # 5. Validate extracted data
            validation_result = await self.validator.validate_document(
                doc_type=doc_type,
                extracted_data=extracted_data,
                context={
                    'fund_id': extracted_data.get('fund_id'),
                    'investor_id': extracted_data.get('investor_id'),
                    'as_of_date': extracted_data.get('as_of_date')
                }
            )
            
            # 6. Calculate overall confidence
            extraction_confidence = self._calculate_extraction_confidence(
                extracted_data.get('extraction_audit', [])
            )
            
            overall_confidence = (
                extraction_confidence * 0.6 +  # Weight extraction confidence
                validation_result.confidence * 0.4  # Weight validation confidence
            )
            
            # 7. Prepare final result
            result = {
                'status': 'success',
                'doc_id': extracted_data['doc_id'],
                'doc_type': doc_type,
                'extracted_data': extracted_data,
                'validation': {
                    'is_valid': validation_result.is_valid,
                    'errors': validation_result.errors,
                    'warnings': validation_result.warnings,
                    'confidence': validation_result.confidence
                },
                'overall_confidence': overall_confidence,
                'requires_review': (
                    overall_confidence < 0.85 or 
                    not validation_result.is_valid or
                    len(validation_result.errors) > 0
                ),
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
            
            # 8. Store extraction audit
            await self._store_extraction_audit(result)
            
            # 9. Store extracted data if valid or confidence is high enough
            if validation_result.is_valid or overall_confidence >= 0.7:
                await self._store_extracted_data(extracted_data, doc_type)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'doc_metadata': doc_metadata
            }
    
    def _calculate_extraction_confidence(self, extraction_audit: List[Dict]) -> float:
        """Calculate overall extraction confidence from audit trail."""
        if not extraction_audit:
            return 0.0
        
        # Weight by field importance
        field_weights = {
            'ending_balance': 1.0,
            'beginning_balance': 1.0,
            'contributions_period': 0.9,
            'distributions_period': 0.9,
            'total_commitment': 0.8,
            'unfunded_commitment': 0.8,
            'management_fees_period': 0.7,
            'realized_gain_loss_period': 0.7,
            'unrealized_gain_loss_period': 0.7,
            'ownership_pct': 0.6
        }
        
        total_weight = 0
        weighted_confidence = 0
        
        for audit_entry in extraction_audit:
            field = audit_entry.get('field')
            confidence = audit_entry.get('confidence', 0)
            weight = field_weights.get(field, 0.5)
            
            weighted_confidence += confidence * weight
            total_weight += weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    async def _store_extraction_audit(self, result: Dict[str, Any]):
        """Store extraction audit trail in database."""
        try:
            doc_id = result.get('doc_id')
            extraction_audit = result.get('extracted_data', {}).get('extraction_audit', [])
            
            for audit_entry in extraction_audit:
                await self.storage.create_extraction_audit(
                    doc_id=doc_id,
                    field_name=audit_entry.get('field'),
                    extracted_value=str(audit_entry.get('value')),
                    extraction_method=audit_entry.get('method'),
                    confidence_score=audit_entry.get('confidence'),
                    validation_status='valid' if result['validation']['is_valid'] else 'invalid',
                    validation_errors=result['validation'].get('errors', [])
                )
        except Exception as e:
            logger.error(f"Error storing extraction audit: {e}")
    
    async def _store_extracted_data(self, extracted_data: Dict[str, Any], doc_type: str):
        """Store extracted data in appropriate PE tables."""
        try:
            if doc_type in ['capital_account_statement', 'quarterly_report']:
                # Store capital account data
                await self.storage.upsert_capital_account(
                    fund_id=extracted_data.get('fund_id'),
                    investor_id=extracted_data.get('investor_id'),
                    as_of_date=extracted_data.get('as_of_date'),
                    data=extracted_data
                )
            
            # Add more storage logic for other document types
            
        except Exception as e:
            logger.error(f"Error storing extracted data: {e}")
    
    async def reprocess_with_corrections(
        self,
        doc_id: str,
        corrections: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reprocess document with manual corrections."""
        try:
            # Get original extraction
            original = await self.storage.get_extraction_by_doc_id(doc_id)
            if not original:
                return {'status': 'error', 'error': 'Original extraction not found'}
            
            # Apply corrections
            corrected_data = original.copy()
            corrected_data.update(corrections)
            
            # Create manual extraction results
            extraction_audit = []
            for field, value in corrections.items():
                extraction_audit.append({
                    'field': field,
                    'value': value,
                    'method': ExtractionMethod.MANUAL,
                    'confidence': 1.0,
                    'corrected_from': original.get(field)
                })
            
            corrected_data['extraction_audit'] = extraction_audit
            corrected_data['manual_corrections'] = True
            corrected_data['correction_timestamp'] = datetime.utcnow().isoformat()
            
            # Re-validate with corrections
            validation_result = await self.validator.validate_document(
                doc_type=original.get('doc_type'),
                extracted_data=corrected_data,
                context={'manual_corrections': True}
            )
            
            # Store corrected data
            result = {
                'status': 'success',
                'doc_id': doc_id,
                'corrected_data': corrected_data,
                'validation': {
                    'is_valid': validation_result.is_valid,
                    'errors': validation_result.errors,
                    'warnings': validation_result.warnings
                }
            }
            
            # Update storage with corrections
            await self._store_extracted_data(corrected_data, original.get('doc_type'))
            
            return result
            
        except Exception as e:
            logger.error(f"Error reprocessing with corrections: {e}")
            return {'status': 'error', 'error': str(e)}