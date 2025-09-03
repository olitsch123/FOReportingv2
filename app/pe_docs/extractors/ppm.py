"""Private Placement Memorandum extractor."""
from typing import Dict, List, Any, Optional
import re

class PPMExtractor:
    """Extract data from Private Placement Memoranda."""
    
    def extract(self, parsed_data: Dict[str, Any], doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fund metadata and investment strategy from PPM.
        """
        result = {
            'fund_metadata': {},
            'strategy': {},
            'risk_factors': [],
            'terms': {}
        }
        
        text = parsed_data.get('text', '')
        
        # Extract fund information
        fund_info = self._extract_fund_info(text)
        result['fund_metadata'].update(fund_info)
        
        # Extract investment strategy
        strategy = self._extract_strategy(text)
        result['strategy'].update(strategy)
        
        # Extract risk factors
        risks = self._extract_risk_factors(text)
        result['risk_factors'].extend(risks)
        
        # Extract terms
        terms = self._extract_terms(text)
        result['terms'].update(terms)
        
        return result
    
    def _extract_fund_info(self, text: str) -> Dict[str, Any]:
        """Extract fund information from PPM."""
        fund_info = {}
        
        # Fund name
        name_patterns = [
            r'fund[:\s]+([^\\n]+fund[^\\n]*)',
            r'offering[:\s]+([^\\n]+)',
            r'investment vehicle[:\s]+([^\\n]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fund_info['fund_name'] = match.group(1).strip()
                break
        
        # Target/maximum size
        size_patterns = [
            r'target size[:\s]+\$?([0-9,]+\.?[0-9]*)\s*(million|billion)?',
            r'maximum offering[:\s]+\$?([0-9,]+\.?[0-9]*)\s*(million|billion)?',
            r'fund size[:\s]+\$?([0-9,]+\.?[0-9]*)\s*(million|billion)?'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    size = float(match.group(1).replace(',', ''))
                    multiplier = match.group(2)
                    if multiplier:
                        if 'million' in multiplier.lower():
                            size *= 1_000_000
                        elif 'billion' in multiplier.lower():
                            size *= 1_000_000_000
                    fund_info['target_size'] = size
                    break
                except ValueError:
                    continue
        
        # Investment focus
        focus_patterns = [
            r'investment focus[:\s]+([^\\n]+)',
            r'strategy[:\s]+([^\\n]+)',
            r'asset class[:\s]+([^\\n]+)'
        ]
        
        for pattern in focus_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fund_info['investment_focus'] = match.group(1).strip()
                break
        
        return fund_info
    
    def _extract_strategy(self, text: str) -> Dict[str, Any]:
        """Extract investment strategy details."""
        strategy = {}
        
        # Geographic focus
        geo_patterns = [
            r'geographic focus[:\s]+([^\\n]+)',
            r'target markets?[:\s]+([^\\n]+)',
            r'regions?[:\s]+([^\\n]+)'
        ]
        
        for pattern in geo_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                strategy['geographic_focus'] = match.group(1).strip()
                break
        
        # Sector focus
        sector_patterns = [
            r'sector focus[:\s]+([^\\n]+)',
            r'industry focus[:\s]+([^\\n]+)',
            r'target sectors?[:\s]+([^\\n]+)'
        ]
        
        for pattern in sector_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                strategy['sector_focus'] = match.group(1).strip()
                break
        
        # Investment size
        size_patterns = [
            r'investment size[:\s]+\$?([0-9,]+\.?[0-9]*)\s*(?:to|\-)\s*\$?([0-9,]+\.?[0-9]*)',
            r'check size[:\s]+\$?([0-9,]+\.?[0-9]*)\s*(?:to|\-)\s*\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    min_size = float(match.group(1).replace(',', ''))
                    max_size = float(match.group(2).replace(',', ''))
                    strategy['min_investment_size'] = min_size
                    strategy['max_investment_size'] = max_size
                    break
                except ValueError:
                    continue
        
        return strategy
    
    def _extract_risk_factors(self, text: str) -> List[str]:
        """Extract risk factors."""
        risks = []
        
        # Look for risk factors section
        risk_section_match = re.search(r'risk factors?([^\\n]*(?:\\n[^\\n]*){0,50})', text, re.IGNORECASE | re.DOTALL)
        
        if risk_section_match:
            risk_text = risk_section_match.group(1)
            
            # Extract bullet points or numbered risks
            risk_patterns = [
                r'(?:^|\\n)\s*[•·-]\s*([^\\n]+)',
                r'(?:^|\\n)\s*\d+\.\s*([^\\n]+)',
                r'(?:^|\\n)\s*\([a-z]\)\s*([^\\n]+)'
            ]
            
            for pattern in risk_patterns:
                matches = re.findall(pattern, risk_text, re.MULTILINE)
                for match in matches:
                    risk = match.strip()
                    if len(risk) > 10:  # Filter out very short matches
                        risks.append(risk)
        
        return risks[:10]  # Limit to top 10 risks
    
    def _extract_terms(self, text: str) -> Dict[str, Any]:
        """Extract key terms from PPM."""
        terms = {}
        
        # Minimum investment
        min_inv_patterns = [
            r'minimum investment[:\s]+\$?([0-9,]+\.?[0-9]*)',
            r'minimum commitment[:\s]+\$?([0-9,]+\.?[0-9]*)'
        ]
        
        for pattern in min_inv_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    min_inv = float(match.group(1).replace(',', ''))
                    terms['minimum_investment'] = min_inv
                    break
                except ValueError:
                    continue
        
        # Fund life
        life_patterns = [
            r'fund life[:\s]+([0-9]+)\s*years?',
            r'term[:\s]+([0-9]+)\s*years?'
        ]
        
        for pattern in life_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    years = int(match.group(1))
                    terms['fund_life_years'] = years
                    break
                except ValueError:
                    continue
        
        return terms

# Global extractor instance
ppm_extractor = PPMExtractor()