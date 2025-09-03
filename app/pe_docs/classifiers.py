"""Document classification for PE documents."""
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from .config import field_library

class DocumentClassifier:
    """Classifies PE documents based on filename and content patterns."""
    
    def __init__(self):
        self.doc_types = {
            'QR': 'Quarterly Report',
            'CAS': 'Capital Account Statement', 
            'CALL': 'Capital Call Notice',
            'DIST': 'Distribution Notice',
            'LPA': 'Limited Partnership Agreement',
            'PPM': 'Private Placement Memorandum',
            'SUBSCRIPTION': 'Subscription Agreement',
            'FINANCIALS': 'Financial Statements',
            'HOLDINGS': 'Holdings Report'
        }
    
    def classify(self, filename: str, content: str) -> Tuple[str, float]:
        """
        Classify document based on filename and content.
        Returns (doc_type, confidence_score).
        """
        filename = filename.lower()
        content_lower = content.lower()[:5000]  # First 5k chars for efficiency
        
        # Filename-based classification
        filename_score = self._classify_by_filename(filename)
        
        # Content-based classification  
        content_score = self._classify_by_content(content_lower)
        
        # Combine scores (weighted)
        combined_scores = {}
        for doc_type in self.doc_types:
            filename_weight = 0.4
            content_weight = 0.6
            combined_scores[doc_type] = (
                filename_score.get(doc_type, 0) * filename_weight +
                content_score.get(doc_type, 0) * content_weight
            )
        
        # Get best match
        best_type = max(combined_scores, key=combined_scores.get)
        best_score = combined_scores[best_type]
        
        # Fallback to generic if confidence too low
        if best_score < 0.3:
            return 'QR', 0.3  # Default to QR with low confidence
        
        return best_type, min(best_score, 0.95)
    
    def _classify_by_filename(self, filename: str) -> Dict[str, float]:
        """Classify based on filename patterns."""
        scores = {}
        
        # Quarterly/Annual Reports
        if any(term in filename for term in ['quarterly', 'quarter', 'q1', 'q2', 'q3', 'q4', 'annual', 'report']):
            scores['QR'] = 0.8
        
        # Capital Account Statement
        if any(term in filename for term in ['capital', 'account', 'statement', 'cas']):
            scores['CAS'] = 0.8
        
        # Call Notice
        if any(term in filename for term in ['call', 'notice', 'contribution']):
            scores['CALL'] = 0.8
            
        # Distribution Notice
        if any(term in filename for term in ['distribution', 'dist', 'payout']):
            scores['DIST'] = 0.8
            
        # Legal documents
        if any(term in filename for term in ['lpa', 'partnership', 'agreement']):
            scores['LPA'] = 0.8
            
        if any(term in filename for term in ['ppm', 'memorandum', 'placement']):
            scores['PPM'] = 0.8
            
        if any(term in filename for term in ['subscription', 'subscribe']):
            scores['SUBSCRIPTION'] = 0.8
            
        # Holdings
        if any(term in filename for term in ['holdings', 'portfolio', 'investments']):
            scores['HOLDINGS'] = 0.7
            
        return scores
    
    def _classify_by_content(self, content: str) -> Dict[str, float]:
        """Classify based on content patterns."""
        scores = {}
        
        # Use phrase bank anchors
        for doc_type, patterns in field_library.phrase_bank.items():
            anchors = patterns.get('anchors', [])
            match_count = 0
            for anchor in anchors:
                if re.search(anchor, content):
                    match_count += 1
            
            if match_count > 0:
                scores[doc_type] = min(0.9, 0.3 + (match_count * 0.2))
        
        # Additional content-based heuristics
        if 'nav reconciliation' in content or 'net asset value' in content:
            scores['QR'] = scores.get('QR', 0) + 0.3
            
        if 'capital account' in content and 'beginning balance' in content:
            scores['CAS'] = scores.get('CAS', 0) + 0.3
            
        if 'call notice' in content or 'capital call' in content:
            scores['CALL'] = scores.get('CALL', 0) + 0.4
            
        if 'distribution notice' in content or 'distribution amount' in content:
            scores['DIST'] = scores.get('DIST', 0) + 0.4
        
        return scores

# Global classifier instance
classifier = DocumentClassifier()