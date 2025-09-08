"""OpenAI-powered intelligent document extraction for PE documents."""

import json
import logging
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import openai

from app.config import load_settings

from .base import BaseExtractor, ExtractionMethod, ExtractionResult

logger = logging.getLogger(__name__)


class OpenAIExtractor(BaseExtractor):
    """OpenAI-powered extraction for complex PE documents with varying formats."""
    
    def __init__(self):
        """Initialize OpenAI extractor."""
        super().__init__()
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY') or load_settings().get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI extraction")
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Use latest model for best accuracy
        
    def _get_field_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define comprehensive field extraction requirements."""
        return {
            'fund_name': {
                'description': 'Name of the fund (e.g., "Oakley Capital Origin II-A SCSp")',
                'type': 'string',
                'required': True
            },
            'investor_name': {
                'description': 'Name of the investor/limited partner',
                'type': 'string', 
                'required': True
            },
            'as_of_date': {
                'description': 'Statement date or period end date (extract as YYYY-MM-DD)',
                'type': 'date',
                'required': True
            },
            'period_type': {
                'description': 'Reporting period type (QUARTERLY, ANNUAL, etc.)',
                'type': 'string',
                'required': False
            },
            'reporting_currency': {
                'description': 'Currency of all amounts (EUR, USD, GBP, etc.)',
                'type': 'string',
                'required': True
            },
            
            # Current Period (Quarter) Data
            'beginning_balance_period': {
                'description': 'Beginning balance for the current period/quarter',
                'type': 'decimal',
                'required': False
            },
            'ending_balance_period': {
                'description': 'Ending balance for the current period/quarter (NAV)',
                'type': 'decimal',
                'required': True
            },
            'contributions_period': {
                'description': 'Capital contributions during the current period',
                'type': 'decimal',
                'required': False
            },
            'distributions_period': {
                'description': 'Distributions during the current period',
                'type': 'decimal',
                'required': False
            },
            'realized_gains_period': {
                'description': 'Realized gains/losses for the current period',
                'type': 'decimal',
                'required': False
            },
            'unrealized_gains_period': {
                'description': 'Unrealized gains/losses for the current period',
                'type': 'decimal',
                'required': False
            },
            'management_fees_period': {
                'description': 'Management fees for the current period',
                'type': 'decimal',
                'required': False
            },
            'other_expenses_period': {
                'description': 'Other expenses for the current period',
                'type': 'decimal',
                'required': False
            },
            
            # Year-to-Date Data
            'beginning_balance_ytd': {
                'description': 'Beginning balance year-to-date',
                'type': 'decimal',
                'required': False
            },
            'ending_balance_ytd': {
                'description': 'Ending balance year-to-date',
                'type': 'decimal',
                'required': False
            },
            'contributions_ytd': {
                'description': 'Total contributions year-to-date',
                'type': 'decimal',
                'required': False
            },
            'distributions_ytd': {
                'description': 'Total distributions year-to-date',
                'type': 'decimal',
                'required': False
            },
            
            # Inception-to-Date Data
            'contributions_itd': {
                'description': 'Total contributions since inception',
                'type': 'decimal',
                'required': False
            },
            'distributions_itd': {
                'description': 'Total distributions since inception',
                'type': 'decimal',
                'required': False
            },
            'realized_gains_itd': {
                'description': 'Total realized gains since inception',
                'type': 'decimal',
                'required': False
            },
            'unrealized_gains_itd': {
                'description': 'Total unrealized gains since inception',
                'type': 'decimal',
                'required': False
            },
            
            # Commitment Information
            'total_commitment': {
                'description': 'Total committed capital amount',
                'type': 'decimal',
                'required': False
            },
            'drawn_commitment': {
                'description': 'Total drawn/called capital',
                'type': 'decimal',
                'required': False
            },
            'undrawn_commitment': {
                'description': 'Remaining undrawn commitment',
                'type': 'decimal',
                'required': False
            },
            
            # Ownership Information
            'ownership_percentage': {
                'description': 'Investor ownership percentage in the fund',
                'type': 'decimal',
                'required': False
            }
        }
    
    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract data using OpenAI with sophisticated prompting."""
        
        try:
            # Create comprehensive extraction prompt
            prompt = self._create_extraction_prompt(text, tables, doc_type)
            
            # Call OpenAI for extraction
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}
            )
            
            # Parse OpenAI response
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Validate and normalize the extracted data
            validated_data = self._validate_and_normalize(extracted_data)
            
            # Add metadata
            validated_data.update({
                'extraction_method': 'openai',
                'model_used': self.model,
                'extraction_timestamp': datetime.utcnow().isoformat(),
                'confidence_score': self._calculate_overall_confidence(validated_data)
            })
            
            logger.info(f"OpenAI extracted {len(validated_data)} fields with model {self.model}")
            return validated_data
            
        except Exception as e:
            logger.error(f"OpenAI extraction failed: {e}")
            return {
                'extraction_error': str(e),
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for OpenAI extraction."""
        return """You are an expert financial analyst specializing in private equity capital account statements. 

Your task is to extract structured financial data from PE documents with high accuracy.

Key capabilities:
- Handle multiple languages (English, German, Spanish)
- Parse various date formats (MM/DD/YYYY, DD.MM.YYYY, Q2 2025, etc.)
- Understand different currency formats (1,234.56, 1.234,56, €, $, £)
- Recognize multi-period data (Period/Quarter, YTD, ITD/Inception)
- Extract from both text and tabular data
- Handle negative values in parentheses: (1,234.56) = -1234.56

Always return valid JSON with extracted values. Use null for missing fields.
For dates, always return YYYY-MM-DD format.
For numbers, return as numeric values (not strings).
For currencies, return the 3-letter code (EUR, USD, GBP).
"""
    
    def _create_extraction_prompt(self, text: str, tables: List[Dict], doc_type: str) -> str:
        """Create a detailed extraction prompt for OpenAI."""
        
        # Format tables for better AI understanding
        table_text = ""
        if tables:
            table_text = "\n\n=== EXTRACTED TABLES ===\n"
            for i, table in enumerate(tables[:3]):  # Limit to first 3 tables
                table_text += f"\nTable {i+1}:\n"
                # Convert table to more readable format
                if isinstance(table, dict) and 'data' in table:
                    table_text += json.dumps(table['data'], indent=2)
                else:
                    table_text += json.dumps(table, indent=2)
                table_text += "\n"
        
        # Create field requirements
        field_requirements = []
        for field_name, field_def in self.field_definitions.items():
            required_text = "REQUIRED" if field_def.get('required', False) else "optional"
            field_requirements.append(f"- {field_name} ({field_def['type']}): {field_def['description']} [{required_text}]")
        
        prompt = f"""Extract the following financial data from this PE capital account statement:

=== DOCUMENT TEXT ===
{text[:4000]}  # Limit text length for token efficiency

{table_text}

=== EXTRACTION REQUIREMENTS ===
{chr(10).join(field_requirements)}

=== SPECIAL INSTRUCTIONS ===

1. **Date Extraction**: 
   - Look for "Q2 2025" and convert to "2025-06-30" (quarter end)
   - Handle "30 June 2025" format
   - Parse various date formats

2. **Multi-Column Tables**:
   - Column 1: Data point names
   - Column 2: Current period/quarter values  
   - Column 3: Year-to-date values
   - Column 4: Inception-to-date values
   - Column 5: Partnership/fund totals
   
3. **Currency Handling**:
   - Detect currency from document (EUR, USD, etc.)
   - Parse numbers with commas: "71,595" = 71595
   - Handle negative values in parentheses: "(14,217)" = -14217
   
4. **Fund and Investor Names**:
   - Extract exact fund name from header or document title
   - Extract investor name (often in header or filename)

5. **Balance Logic**:
   - Use the investor-specific columns (usually column 2 for period, column 3 for YTD)
   - Don't use partnership totals for individual investor data
   
6. **Missing Data**:
   - Return null for fields that cannot be found
   - Don't guess or calculate missing values

Return a JSON object with the extracted fields. Example:
{{
  "fund_name": "Oakley Capital Origin II-A SCSp",
  "investor_name": "Brainweb Investment GmbH", 
  "as_of_date": "2025-06-30",
  "period_type": "QUARTERLY",
  "reporting_currency": "EUR",
  "ending_balance_period": 71595,
  "total_commitment": 5000000,
  "drawn_commitment": 300000,
  "undrawn_commitment": 4700000
}}
"""
        
        return prompt
    
    def _validate_and_normalize(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize extracted data."""
        normalized = {}
        
        for field_name, value in extracted_data.items():
            if field_name not in self.field_definitions:
                continue
                
            field_def = self.field_definitions[field_name]
            field_type = field_def['type']
            
            # Validate and convert based on field type
            if field_type == 'date':
                normalized_value = self._normalize_date(value)
            elif field_type == 'decimal':
                normalized_value = self._normalize_decimal(value)
            elif field_type == 'string':
                normalized_value = str(value) if value is not None else None
            else:
                normalized_value = value
            
            if normalized_value is not None:
                normalized[field_name] = normalized_value
        
        return normalized
    
    def _normalize_date(self, value: Any) -> Optional[str]:
        """Normalize date to YYYY-MM-DD format."""
        if value is None:
            return None
            
        try:
            from dateutil import parser
            if isinstance(value, str):
                # Handle quarter format
                quarter_match = re.search(r'Q([1-4])\s*(\d{4})', value, re.IGNORECASE)
                if quarter_match:
                    quarter, year = quarter_match.groups()
                    quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
                    return f"{year}-{quarter_ends[quarter]}"
                
                # Parse other formats
                parsed = parser.parse(value)
                return parsed.strftime('%Y-%m-%d')
            
            elif isinstance(value, date):
                return value.strftime('%Y-%m-%d')
                
        except Exception as e:
            logger.warning(f"Could not normalize date '{value}': {e}")
            
        return None
    
    def _normalize_decimal(self, value: Any) -> Optional[float]:
        """Normalize decimal values."""
        if value is None:
            return None
            
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            if isinstance(value, str):
                # Remove currency symbols and spaces
                cleaned = re.sub(r'[€$£\s]', '', value)
                
                # Handle parentheses as negative
                if cleaned.startswith('(') and cleaned.endswith(')'):
                    cleaned = '-' + cleaned[1:-1]
                
                # Handle German number format (1.234,56)
                if ',' in cleaned and '.' in cleaned:
                    if cleaned.rindex(',') > cleaned.rindex('.'):
                        # German format: 1.234,56
                        cleaned = cleaned.replace('.', '').replace(',', '.')
                    # else: US format: 1,234.56 (remove commas)
                    else:
                        cleaned = cleaned.replace(',', '')
                elif ',' in cleaned:
                    # Could be German decimal or US thousands
                    # If only one comma and it's near the end, treat as German decimal
                    comma_pos = cleaned.index(',')
                    if len(cleaned) - comma_pos <= 3:
                        cleaned = cleaned.replace(',', '.')
                    else:
                        cleaned = cleaned.replace(',', '')
                
                return float(cleaned)
                
        except Exception as e:
            logger.warning(f"Could not normalize decimal '{value}': {e}")
            
        return None
    
    def _calculate_overall_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """Calculate overall confidence score."""
        required_fields = [name for name, def_ in self.field_definitions.items() if def_.get('required', False)]
        found_required = sum(1 for field in required_fields if field in extracted_data and extracted_data[field] is not None)
        
        if not required_fields:
            return 0.8
        
        base_confidence = found_required / len(required_fields)
        
        # Bonus for finding optional fields
        optional_fields = [name for name, def_ in self.field_definitions.items() if not def_.get('required', False)]
        found_optional = sum(1 for field in optional_fields if field in extracted_data and extracted_data[field] is not None)
        
        if optional_fields:
            optional_bonus = (found_optional / len(optional_fields)) * 0.2
            base_confidence += optional_bonus
        
        return min(base_confidence, 1.0)


class OpenAICapitalAccountExtractor(OpenAIExtractor):
    """Specialized OpenAI extractor for capital account statements."""
    
    def _get_system_prompt(self) -> str:
        """Specialized system prompt for capital account statements."""
        return """You are an expert private equity financial analyst specializing in capital account statements.

You excel at extracting structured data from complex multi-column capital account statements that vary by fund manager.

Key expertise:
- Multi-period data extraction (Quarter, YTD, ITD/Inception)
- Multi-column table interpretation (investor-specific vs partnership totals)
- Various fund formats (different managers have different layouts)
- Currency and number format handling (EUR/USD, German/US formats)
- Date parsing (quarters, specific dates, period endings)

CRITICAL RULES:
1. Extract INVESTOR-SPECIFIC data, not partnership totals
2. For multi-column tables, use investor columns (typically columns 2-4), NOT the partnership total column
3. Parse negative values in parentheses correctly: (14,217) = -14217
4. Convert quarters to quarter-end dates: Q2 2025 = 2025-06-30
5. Always specify the currency found in the document
6. Return null for any field you cannot confidently extract

Return structured JSON with extracted financial data."""

    async def extract(self, text: str, tables: List[Dict], doc_type: str) -> Dict[str, Any]:
        """Extract capital account data with enhanced prompting."""
        
        try:
            # Enhanced prompt specifically for capital account statements
            prompt = f"""Extract investor-specific financial data from this capital account statement:

=== DOCUMENT CONTENT ===
{text[:5000]}

=== TABLE DATA ===
{json.dumps(tables[:2], indent=2) if tables else "No structured tables found"}

=== EXTRACTION TASK ===
This appears to be a capital account statement. Please extract:

**Document Metadata:**
- fund_name: Exact fund name from document header
- investor_name: Investor/LP name 
- as_of_date: Statement date (convert Q2 2025 to 2025-06-30)
- reporting_currency: Currency used (EUR, USD, etc.)

**Financial Data (INVESTOR-SPECIFIC only, not partnership totals):**
- ending_balance_period: Current period ending NAV/balance
- beginning_balance_period: Period beginning balance
- contributions_period: Capital calls/contributions this period
- distributions_period: Distributions received this period
- contributions_ytd: Year-to-date contributions
- distributions_ytd: Year-to-date distributions
- contributions_itd: Total contributions since inception
- distributions_itd: Total distributions since inception
- total_commitment: Total committed capital
- drawn_commitment: Total drawn capital
- undrawn_commitment: Remaining commitment
- ownership_percentage: Investor's ownership %

**IMPORTANT NOTES:**
- Use investor-specific columns from tables, NOT partnership totals
- Handle negative values in parentheses: (14,217) = -14217
- Parse German number formats: 1.234,56 = 1234.56
- Convert Q2 2025 to 2025-06-30
- Return numeric values, not strings
- Use null for missing data

Return JSON with extracted fields."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            # Parse and validate response
            extracted_data = json.loads(response.choices[0].message.content)
            validated_data = self._validate_and_normalize(extracted_data)
            
            # Add extraction metadata
            validated_data.update({
                'extraction_method': 'openai',
                'model_used': self.model,
                'extraction_timestamp': datetime.utcnow().isoformat(),
                'confidence_score': self._calculate_overall_confidence(validated_data)
            })
            
            logger.info(f"OpenAI capital account extraction completed: {len(validated_data)} fields")
            return validated_data
            
        except Exception as e:
            logger.error(f"OpenAI capital account extraction failed: {e}")
            return {
                'extraction_error': str(e),
                'extraction_method': 'openai_failed',
                'extraction_timestamp': datetime.utcnow().isoformat()
            }