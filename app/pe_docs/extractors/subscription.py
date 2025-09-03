"""Subscription Agreement extractor."""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re

class SubscriptionExtractor:
    """Extract data from Subscription Agreements."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract investor commitment and subscription details.
        """
        result = {
            'investor_metadata': {},
            'commitment': {},
            'subscription_details': {}
        }
        
        text = parsed_data.get('text', '')
        
        # Extract investor information
        investor_info = self._extract_investor_info(text)
        result['investor_metadata'].update(investor_info)
        
        # Extract commitment details
        commitment = self._extract_commitment(text)
        result['commitment'].update(commitment)
        
        # Extract subscription details
        subscription = self._extract_subscription_details(text)
        result['subscription_details'].update(subscription)
        
        return result
    
    def _extract_investor_info(self, text: str) -> Dict[str, Any]:
        """Extract investor information."""
        investor_info = {}
        
        # Investor name patterns
        name_patterns = [
            r'investor[:\s]+([^\\n]+)',
            r'limited partner[:\s]+([^\\n]+)',
            r'subscriber[:\s]+([^\\n]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                investor_info['investor_name'] = match.group(1).strip()
                break
        
        # Investor type
        type_patterns = [
            r'investor type[:\s]+([^\\n]+)',
            r'entity type[:\s]+([^\\n]+)'
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                investor_info['investor_type'] = match.group(1).strip()
                break
        
        return investor_info
    
    def _extract_commitment(self, text: str) -> Dict[str, Any]:
        """Extract commitment amount and terms."""
        commitment = {}
        
        # Commitment amount patterns
        amount_patterns = [
            r'commitment amount[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'capital commitment[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'subscription amount[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1).replace(',', ''))
                    commitment['commitment_amount'] = amount
                    break
                except ValueError:
                    continue
        
        # Currency
        currency_patterns = [
            r'currency[:\s]+([A-Z]{3})',
            r'denomination[:\s]+([A-Z]{3})'
        ]
        
        for pattern in currency_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                commitment['currency'] = match.group(1).upper()
                break
        
        # Default to EUR if not found
        if 'currency' not in commitment:
            if '$' in text:
                commitment['currency'] = 'USD'
            elif '€' in text:
                commitment['currency'] = 'EUR'
            elif '£' in text:
                commitment['currency'] = 'GBP'
            else:
                commitment['currency'] = 'EUR'  # Default
        
        return commitment
    
    def _extract_subscription_details(self, text: str) -> Dict[str, Any]:
        """Extract subscription-specific details."""
        details = {}
        
        # Subscription date
        date_patterns = [
            r'subscription date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'effective date[:\s]+([a-zA-Z]+ \d{1,2},? \d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                subscription_date = self._parse_date(match.group(1))
                if subscription_date:
                    details['subscription_date'] = subscription_date
                    break
        
        # Side letter references
        if re.search(r'side letter', text, re.IGNORECASE):
            details['has_side_letter'] = True
        
        # Special terms
        if re.search(r'most favored nation', text, re.IGNORECASE):
            details['mfn_clause'] = True
        
        return details
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats."""
        if not date_str or str(date_str).strip() in ['', 'nan', 'None']:
            return None
        
        date_str = str(date_str).strip()
        
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y', 
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None

# Global extractor instance
subscription_extractor = SubscriptionExtractor()