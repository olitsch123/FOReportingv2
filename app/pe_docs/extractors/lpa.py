"""Limited Partnership Agreement extractor."""
from typing import Dict, List, Any, Optional
import re

class LPAExtractor:
    """Extract data from Limited Partnership Agreements."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fund metadata and terms from LPA.
        """
        result = {
            'fund_metadata': {},
            'investor_metadata': {},
            'terms': {}
        }
        
        text = parsed_data.get('text', '')
        
        # Extract fund information
        fund_info = self._extract_fund_info(text)
        result['fund_metadata'].update(fund_info)
        
        # Extract terms and conditions
        terms = self._extract_terms(text)
        result['terms'].update(terms)
        
        return result
    
    def _extract_fund_info(self, text: str) -> Dict[str, Any]:
        """Extract basic fund information."""
        fund_info = {}
        
        # Fund name patterns
        name_patterns = [
            r'fund name[:\s]+([^\\n]+)',
            r'partnership[:\s]+([^\\n]+)',
            r'limited partnership[:\s]+([^\\n]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fund_info['fund_name'] = match.group(1).strip()
                break
        
        # Management company
        mgmt_patterns = [
            r'general partner[:\s]+([^\\n]+)',
            r'management company[:\s]+([^\\n]+)',
            r'investment manager[:\s]+([^\\n]+)'
        ]
        
        for pattern in mgmt_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fund_info['management_company'] = match.group(1).strip()
                break
        
        # Target size
        size_patterns = [
            r'target size[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'maximum size[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'fund size[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    size = float(match.group(1).replace(',', ''))
                    fund_info['target_size'] = size
                    break
                except ValueError:
                    continue
        
        return fund_info
    
    def _extract_terms(self, text: str) -> Dict[str, Any]:
        """Extract key terms and conditions."""
        terms = {}
        
        # Management fee
        mgmt_fee_patterns = [
            r'management fee[:\s]+([0-9]+\.?[0-9]*)\s*%',
            r'annual fee[:\s]+([0-9]+\.?[0-9]*)\s*%'
        ]
        
        for pattern in mgmt_fee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    fee_pct = float(match.group(1))
                    terms['management_fee_pct'] = fee_pct / 100  # Convert to decimal
                    break
                except ValueError:
                    continue
        
        # Carried interest
        carry_patterns = [
            r'carried interest[:\s]+([0-9]+\.?[0-9]*)\s*%',
            r'performance fee[:\s]+([0-9]+\.?[0-9]*)\s*%'
        ]
        
        for pattern in carry_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    carry_pct = float(match.group(1))
                    terms['carried_interest_pct'] = carry_pct / 100
                    break
                except ValueError:
                    continue
        
        # Investment period
        period_patterns = [
            r'investment period[:\s]+([0-9]+)\s*years?',
            r'commitment period[:\s]+([0-9]+)\s*years?'
        ]
        
        for pattern in period_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    years = int(match.group(1))
                    terms['investment_period_years'] = years
                    break
                except ValueError:
                    continue
        
        return terms

# Global extractor instance
lpa_extractor = LPAExtractor()