"""AI-powered field matching for intelligent document extraction."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import openai

from app.config import settings

logger = logging.getLogger(__name__)


class AIFieldMatcher:
    """Use AI to intelligently match extracted text to database fields."""
    
    def __init__(self):
        """Initialize AI field matcher with OpenAI."""
        import os
        api_key = os.getenv('OPENAI_API_KEY') or settings.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment or settings")
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4-turbo-preview"
        
        # Load field mappings and context
        self.field_context = self._load_field_context()
        
    def _load_field_context(self) -> Dict[str, Any]:
        """Load field definitions and context for AI matching."""
        return {
            'capital_account': {
                'beginning_balance': {
                    'aliases': ['opening balance', 'prior balance', 'balance beginning', 'anfangsbestand', 'saldo inicial'],
                    'description': 'The starting balance for the period',
                    'type': 'currency'
                },
                'ending_balance': {
                    'aliases': ['closing balance', 'nav', 'net asset value', 'balance ending', 'endbestand', 'saldo final'],
                    'description': 'The ending balance for the period',
                    'type': 'currency'
                },
                'contributions_period': {
                    'aliases': ['capital calls', 'contributions', 'paid in capital', 'einzahlungen', 'aportaciones'],
                    'description': 'Total contributions/capital calls during the period',
                    'type': 'currency'
                },
                'distributions_period': {
                    'aliases': ['distributions', 'dividends', 'payouts', 'ausschüttungen', 'distribuciones'],
                    'description': 'Total distributions during the period',
                    'type': 'currency'
                },
                'as_of_date': {
                    'aliases': ['reporting date', 'statement date', 'as at', 'stand', 'fecha'],
                    'description': 'The date of the statement',
                    'type': 'date'
                },
                'currency': {
                    'aliases': ['reporting currency', 'ccy', 'währung', 'moneda'],
                    'description': 'The currency of the amounts',
                    'type': 'currency_code'
                }
            }
        }
    
    async def match_fields(
        self, 
        extracted_text: str, 
        tables: List[Dict],
        doc_type: str
    ) -> Dict[str, Any]:
        """Use AI to match extracted text to database fields."""
        
        # Prepare context for AI
        field_definitions = self.field_context.get(doc_type, {})
        
        # Create prompt for AI field matching
        prompt = self._create_matching_prompt(extracted_text, tables, field_definitions)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a financial document expert specializing in private equity statements. 
                        Your task is to accurately match extracted text to database fields.
                        Consider multiple languages (English, German, Spanish) and various financial formats.
                        Always return valid JSON with field names as keys and extracted values."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}
            )
            
            # Parse AI response
            ai_matches = json.loads(response.choices[0].message.content)
            
            # Validate and normalize extracted values
            validated_matches = self._validate_ai_matches(ai_matches, field_definitions)
            
            # Add confidence scores
            for field, value in validated_matches.items():
                if value is not None:
                    validated_matches[f"{field}_confidence"] = self._calculate_confidence(
                        field, value, extracted_text
                    )
            
            logger.info(f"AI matched {len(validated_matches)} fields with high confidence")
            return validated_matches
            
        except Exception as e:
            logger.error(f"AI field matching failed: {e}")
            return {}
    
    def _create_matching_prompt(
        self, 
        text: str, 
        tables: List[Dict],
        field_definitions: Dict
    ) -> str:
        """Create a detailed prompt for AI field matching."""
        
        # Format field definitions for prompt
        field_info = []
        for field_name, definition in field_definitions.items():
            field_info.append(
                f"- {field_name}: {definition['description']} "
                f"(aliases: {', '.join(definition['aliases'])})"
            )
        
        # Format tables if available
        table_text = ""
        if tables:
            table_text = "\n\nExtracted Tables:\n"
            for i, table in enumerate(tables[:3]):  # Limit to first 3 tables
                table_text += f"\nTable {i+1}:\n{json.dumps(table, indent=2)}\n"
        
        prompt = f"""Extract the following financial fields from this document:

{chr(10).join(field_info)}

Document Text:
{text[:3000]}  # Limit text length

{table_text}

Instructions:
1. Look for each field using the main name and all aliases
2. Handle multiple currencies (EUR, USD, GBP) and formats (1,234.56 or 1.234,56)
3. For dates, parse various formats (MM/DD/YYYY, DD.MM.YYYY, etc.)
4. If a value appears multiple times, use the most recent/prominent one
5. Return NULL for fields that cannot be found
6. Ensure all currency values are returned as numbers (not strings)

Return a JSON object with field names as keys and extracted values.
Example: {{"beginning_balance": 1234567.89, "currency": "EUR", "as_of_date": "2024-12-31"}}
"""
        
        return prompt
    
    def _validate_ai_matches(
        self, 
        ai_matches: Dict[str, Any],
        field_definitions: Dict
    ) -> Dict[str, Any]:
        """Validate and normalize AI-extracted values."""
        validated = {}
        
        for field_name, value in ai_matches.items():
            if field_name not in field_definitions:
                continue
                
            field_type = field_definitions[field_name]['type']
            
            # Validate based on field type
            if field_type == 'currency':
                validated_value = self._validate_currency(value)
            elif field_type == 'date':
                validated_value = self._validate_date(value)
            elif field_type == 'currency_code':
                validated_value = self._validate_currency_code(value)
            else:
                validated_value = value
            
            if validated_value is not None:
                validated[field_name] = validated_value
        
        return validated
    
    def _validate_currency(self, value: Any) -> Optional[float]:
        """Validate and normalize currency values."""
        if value is None:
            return None
            
        try:
            # Handle various formats
            if isinstance(value, (int, float)):
                return float(value)
            
            if isinstance(value, str):
                # Remove currency symbols and spaces
                cleaned = re.sub(r'[€$£\s,]', '', value)
                # Handle German format (1.234,56)
                if ',' in cleaned and cleaned.count(',') == 1:
                    if cleaned.index(',') > cleaned.rfind('.'):
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                return float(cleaned)
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Could not parse currency value '{value}': {e}")
            
        return None
    
    def _validate_date(self, value: Any) -> Optional[str]:
        """Validate and normalize date values."""
        if value is None:
            return None
            
        try:
            # Parse various date formats
            from dateutil import parser
            parsed_date = parser.parse(str(value))
            return parsed_date.strftime('%Y-%m-%d')
        except (ValueError, TypeError, ImportError, AttributeError) as e:
            logger.warning(f"Could not parse date value '{value}': {e}")
            
        return None
    
    def _validate_currency_code(self, value: Any) -> Optional[str]:
        """Validate currency codes."""
        if value is None:
            return None
            
        valid_codes = ['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CAD', 'AUD']
        
        if isinstance(value, str):
            code = value.upper().strip()
            if code in valid_codes:
                return code
        
        return None
    
    def _calculate_confidence(self, field: str, value: Any, text: str) -> float:
        """Calculate confidence score for extracted value."""
        # Simple confidence calculation based on value presence in text
        confidence = 0.5
        
        if value is not None:
            value_str = str(value)
            if value_str in text:
                confidence = 0.9
            elif value_str.replace('.', ',') in text:
                confidence = 0.85
            elif value_str.replace(',', '.') in text:
                confidence = 0.85
        
        return confidence