"""Document classification for PE documents."""

import re
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import openai
from structlog import get_logger
from app.config import load_settings
from app.pe_docs.config import get_pe_config

logger = get_logger()
settings = load_settings()
pe_config = get_pe_config()


class PEDocumentClassifier:
    """Classify PE documents into specific types."""
    
    # Document type mappings
    DOC_TYPES = {
        'QR': 'quarterly_report',
        'AR': 'annual_report', 
        'CAS': 'capital_account_statement',
        'CALL': 'capital_call_notice',
        'DIST': 'distribution_notice',
        'LPA': 'limited_partnership_agreement',
        'PPM': 'private_placement_memorandum',
        'SUBSCRIPTION': 'subscription_agreement',
        'FINANCIALS': 'financial_statement',
        'HOLDINGS': 'holdings_report'
    }
    
    def __init__(self):
        """Initialize classifier."""
        self.client = openai.OpenAI(api_key=settings.get("OPENAI_API_KEY"))
        self.model = settings.get("OPENAI_LLM_MODEL", "gpt-4")
    
    def classify(self, 
                 text: str, 
                 filename: str,
                 first_pages: Optional[str] = None) -> Tuple[str, float]:
        """
        Classify document type using heuristics and LLM fallback.
        
        Returns:
            Tuple of (doc_type, confidence_score)
        """
        # Try heuristic classification first
        doc_type, confidence = self._heuristic_classify(text, filename)
        
        if confidence >= 0.8:
            logger.info(
                "pe_doc_classified_heuristic",
                doc_type=doc_type,
                confidence=confidence,
                filename=filename
            )
            return doc_type, confidence
        
        # Use LLM for uncertain cases
        doc_type_llm, confidence_llm = self._llm_classify(
            text[:5000],  # First 5000 chars
            filename
        )
        
        # Combine results
        if confidence_llm > confidence:
            doc_type, confidence = doc_type_llm, confidence_llm
        
        logger.info(
            "pe_doc_classified",
            doc_type=doc_type,
            confidence=confidence,
            filename=filename,
            method="combined"
        )
        
        return doc_type, confidence
    
    def _heuristic_classify(self, text: str, filename: str) -> Tuple[str, float]:
        """Classify using filename patterns and text anchors."""
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Check each document type
        scores = {}
        
        for doc_key, doc_type in self.DOC_TYPES.items():
            score = 0.0
            
            # Check filename patterns
            if doc_key.lower() in filename_lower:
                score += 0.4
            
            # Check document type specific patterns
            if doc_type in filename_lower.replace('_', ' '):
                score += 0.3
            
            # Check text anchors from phrase bank
            anchors = pe_config.get_doc_type_anchors(doc_key)
            for anchor in anchors:
                if re.search(anchor, text_lower):
                    score += 0.3
                    break
            
            # Additional patterns
            patterns = self._get_doc_patterns(doc_key)
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 0.2
            
            scores[doc_type] = min(score, 1.0)
        
        # Get highest scoring type
        if scores:
            best_type = max(scores, key=scores.get)
            return best_type, scores[best_type]
        
        return 'other', 0.0
    
    def _get_doc_patterns(self, doc_type: str) -> List[str]:
        """Get regex patterns for document type."""
        patterns = {
            'QR': [
                r'quarterly\s+report',
                r'q[1-4]\s+20\d{2}',
                r'three\s+months\s+ended'
            ],
            'AR': [
                r'annual\s+report',
                r'year\s+ended',
                r'fiscal\s+year\s+20\d{2}'
            ],
            'CAS': [
                r'capital\s+account',
                r'partner\s+capital',
                r'capital\s+balance'
            ],
            'CALL': [
                r'capital\s+call',
                r'call\s+notice',
                r'contribution\s+notice'
            ],
            'DIST': [
                r'distribution\s+notice',
                r'proceeds\s+distribution',
                r'distribution\s+payment'
            ],
            'LPA': [
                r'limited\s+partnership\s+agreement',
                r'partnership\s+agreement',
                r'amended\s+and\s+restated'
            ],
            'PPM': [
                r'private\s+placement',
                r'offering\s+memorandum',
                r'confidential\s+memorandum'
            ],
            'SUBSCRIPTION': [
                r'subscription\s+agreement',
                r'subscription\s+document',
                r'investor\s+subscription'
            ]
        }
        return patterns.get(doc_type, [])
    
    def _llm_classify(self, text: str, filename: str) -> Tuple[str, float]:
        """Use LLM for classification."""
        try:
            prompt = f"""Classify this financial document into one of these types:
- QR: Quarterly Report
- AR: Annual Report  
- CAS: Capital Account Statement
- CALL: Capital Call Notice
- DIST: Distribution Notice
- LPA: Limited Partnership Agreement
- PPM: Private Placement Memorandum
- SUBSCRIPTION: Subscription Agreement
- FINANCIALS: Financial Statement
- HOLDINGS: Holdings Report
- OTHER: Other document type

Filename: {filename}
Text excerpt:
{text[:2000]}

Respond with JSON: {{"doc_type": "TYPE", "confidence": 0.0-1.0, "reason": "brief explanation"}}
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial document classification expert."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            result = eval(response.choices[0].message.content)
            doc_key = result.get('doc_type', 'OTHER')
            confidence = float(result.get('confidence', 0.5))
            
            # Map to our doc type
            doc_type = self.DOC_TYPES.get(doc_key, 'other')
            
            return doc_type, confidence
            
        except Exception as e:
            logger.error(
                "llm_classification_failed",
                error=str(e),
                filename=filename
            )
            return 'other', 0.0
    
    def extract_metadata(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract document metadata based on type."""
        metadata = {}
        
        # Extract common metadata
        metadata.update(self._extract_dates(text))
        metadata.update(self._extract_fund_info(text))
        metadata.update(self._extract_amounts(text))
        
        # Type-specific extraction
        if doc_type in ['quarterly_report', 'annual_report']:
            metadata.update(self._extract_performance_metrics(text))
        elif doc_type == 'capital_account_statement':
            metadata.update(self._extract_capital_account_data(text))
        elif doc_type in ['capital_call_notice', 'distribution_notice']:
            metadata.update(self._extract_transaction_data(text))
        
        return metadata
    
    def _extract_dates(self, text: str) -> Dict[str, Any]:
        """Extract date information."""
        dates = {}
        
        # As of date pattern
        as_of_pattern = r'as\s+of\s+(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})'
        match = re.search(as_of_pattern, text, re.IGNORECASE)
        if match:
            dates['as_of_date'] = match.group(1)
        
        # Period patterns
        period_pattern = r'(quarter|year)\s+ended\s+(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})'
        match = re.search(period_pattern, text, re.IGNORECASE)
        if match:
            dates['period_end_date'] = match.group(2)
            dates['period_type'] = match.group(1).lower()
        
        return dates
    
    def _extract_fund_info(self, text: str) -> Dict[str, Any]:
        """Extract fund information."""
        info = {}
        
        # Fund name patterns
        fund_patterns = [
            r'fund\s*:\s*([^\n]+)',
            r'partnership\s*:\s*([^\n]+)',
            r'fund\s+name\s*:\s*([^\n]+)'
        ]
        
        for pattern in fund_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['fund_name'] = match.group(1).strip()
                break
        
        return info
    
    def _extract_amounts(self, text: str) -> Dict[str, Any]:
        """Extract monetary amounts."""
        amounts = {}
        
        # Currency pattern
        currency_pattern = r'(USD|EUR|GBP|CHF|JPY|\$|€|£)'
        match = re.search(currency_pattern, text)
        if match:
            currency = match.group(1)
            # Map symbols to codes
            symbol_map = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
            amounts['currency'] = symbol_map.get(currency, currency)
        
        return amounts
    
    def _extract_performance_metrics(self, text: str) -> Dict[str, Any]:
        """Extract performance metrics from reports."""
        metrics = {}
        
        # IRR pattern
        irr_pattern = r'irr\s*:?\s*([-]?\d+\.?\d*)\s*%'
        match = re.search(irr_pattern, text, re.IGNORECASE)
        if match:
            metrics['irr'] = float(match.group(1)) / 100
        
        # MOIC pattern
        moic_pattern = r'moic\s*:?\s*(\d+\.?\d*)x?'
        match = re.search(moic_pattern, text, re.IGNORECASE)
        if match:
            metrics['moic'] = float(match.group(1))
        
        # DPI pattern
        dpi_pattern = r'dpi\s*:?\s*(\d+\.?\d*)x?'
        match = re.search(dpi_pattern, text, re.IGNORECASE)
        if match:
            metrics['dpi'] = float(match.group(1))
        
        return metrics
    
    def _extract_capital_account_data(self, text: str) -> Dict[str, Any]:
        """Extract capital account specific data."""
        data = {}
        
        # Beginning balance
        begin_pattern = r'beginning\s+balance\s*:?\s*\$?\s*([\d,]+\.?\d*)'
        match = re.search(begin_pattern, text, re.IGNORECASE)
        if match:
            data['beginning_balance'] = float(match.group(1).replace(',', ''))
        
        # Ending balance
        end_pattern = r'ending\s+balance\s*:?\s*\$?\s*([\d,]+\.?\d*)'
        match = re.search(end_pattern, text, re.IGNORECASE)
        if match:
            data['ending_balance'] = float(match.group(1).replace(',', ''))
        
        return data
    
    def _extract_transaction_data(self, text: str) -> Dict[str, Any]:
        """Extract transaction data from notices."""
        data = {}
        
        # Amount pattern
        amount_pattern = r'amount\s*:?\s*\$?\s*([\d,]+\.?\d*)'
        match = re.search(amount_pattern, text, re.IGNORECASE)
        if match:
            data['transaction_amount'] = float(match.group(1).replace(',', ''))
        
        # Due date pattern
        due_pattern = r'due\s+date\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})'
        match = re.search(due_pattern, text, re.IGNORECASE)
        if match:
            data['due_date'] = match.group(1)
        
        return data