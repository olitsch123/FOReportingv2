"""Universal OpenAI-powered document intelligence for all PE document types."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import openai

from app.config import load_settings
from app.exceptions import OpenAIError, ExtractionError, ConfigurationError

logger = logging.getLogger(__name__)


class OpenAIUniversalExtractor:
    """Universal OpenAI-powered extractor for all PE document types."""
    
    def __init__(self):
        """Initialize OpenAI universal extractor."""
        api_key = os.getenv('OPENAI_API_KEY') or load_settings().get('OPENAI_API_KEY')
        if not api_key:
            raise ConfigurationError(
                config_key="OPENAI_API_KEY",
                reason="OpenAI API key is required for document extraction"
            )
        
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4o"
        
    async def extract_and_classify(
        self, 
        text: str, 
        tables: List[Dict], 
        filename: str,
        file_path: str
    ) -> Dict[str, Any]:
        """Extract all data using OpenAI with document intelligence."""
        
        try:
            # Create comprehensive prompt
            prompt = self._create_comprehensive_prompt(text, tables, filename)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.05,  # Very low for maximum consistency
                response_format={"type": "json_object"}
            )
            
            # Parse response
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Validate and ensure required fields
            validated_data = self._ensure_required_fields(extracted_data, filename)
            
            # Add metadata
            validated_data.update({
                'extraction_method': 'openai_universal',
                'model_used': self.model,
                'extraction_timestamp': datetime.utcnow().isoformat(),
                'file_path': file_path,
                'filename': filename
            })
            
            logger.info(f"OpenAI universal extraction: {validated_data.get('doc_type', 'unknown')} document, {len(validated_data)} fields")
            return validated_data
            
        except Exception as e:
            logger.error(f"OpenAI universal extraction failed: {e}")
            return {
                'extraction_error': str(e),
                'extraction_method': 'openai_failed',
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
    
    def _get_system_prompt(self) -> str:
        """Comprehensive system prompt for document intelligence."""
        return """You are an expert private equity financial analyst with deep expertise in fund documents.

You excel at:
- Document classification (capital account statements, quarterly reports, capital calls, distributions, etc.)
- Multi-column table interpretation with period-specific data (Quarter, YTD, ITD)
- Complex financial data extraction from varying fund manager formats
- Multi-language support (English, German, Spanish)
- Date parsing and period identification
- Currency and number format handling

CRITICAL CAPABILITIES:
1. **Document Type Recognition**: Accurately classify PE document types
2. **Multi-Period Data**: Extract Quarter, YTD, and Inception-to-Date figures
3. **Investor vs Partnership Data**: Distinguish between investor-specific and total fund data
4. **Date Intelligence**: Parse quarters, specific dates, period endings
5. **Format Handling**: Handle varying fund manager document layouts
6. **Data Validation**: Ensure logical consistency in extracted data

EXTRACTION RULES:
- Always extract investor-specific data, NOT partnership totals
- For multi-column tables: use investor columns (typically 2-4), ignore total column
- Parse negative values in parentheses: (14,217) = -14217
- Handle both US (1,234.56) and German (1.234,56) number formats
- Convert quarters to quarter-end dates: Q2 2025 = 2025-06-30
- Extract fund and investor names from headers/titles
- Always specify currency found in document
- Return null only if data truly cannot be found

Return comprehensive JSON with all extracted financial and metadata."""
    
    def _create_comprehensive_prompt(self, text: str, tables: List[Dict], filename: str) -> str:
        """Create comprehensive extraction prompt."""
        
        # Format tables for AI
        table_text = ""
        if tables:
            table_text = "\n\n=== STRUCTURED TABLES ===\n"
            for i, table in enumerate(tables[:3]):
                table_text += f"\nTable {i+1}:\n{json.dumps(table, indent=2)}\n"
        
        prompt = f"""DOCUMENT ANALYSIS TASK

=== FILENAME ===
{filename}

=== DOCUMENT TEXT ===
{text[:6000]}

{table_text}

=== EXTRACTION REQUIREMENTS ===

Please extract ALL available data from this PE document. Based on the content, determine:

**1. DOCUMENT METADATA:**
- doc_type: Document classification (capital_account_statement, quarterly_report, capital_call_notice, distribution_notice, etc.)
- fund_name: Exact fund name from document
- investor_name: Investor/Limited Partner name
- as_of_date: Statement/reporting date (YYYY-MM-DD format)
- period_type: QUARTERLY, ANNUAL, etc.
- reporting_currency: Currency code (EUR, USD, GBP)

**2. FINANCIAL DATA (Extract ALL periods if available):**

**Current Period/Quarter:**
- beginning_balance: Period beginning balance
- ending_balance: Period ending balance/NAV  
- contributions_period: Capital contributions this period
- distributions_period: Distributions this period
- realized_gain_loss_period: Realized gains/losses
- unrealized_gain_loss_period: Unrealized gains/losses
- management_fees_period: Management fees
- partnership_expenses_period: Other expenses

**Year-to-Date:**
- contributions_ytd: YTD contributions
- distributions_ytd: YTD distributions
- realized_gain_loss_ytd: YTD realized gains/losses
- unrealized_gain_loss_ytd: YTD unrealized gains/losses

**Inception-to-Date/Cumulative:**
- contributions_itd: Total contributions since inception
- distributions_itd: Total distributions since inception
- realized_gain_loss_itd: Total realized gains since inception
- unrealized_gain_loss_itd: Total unrealized gains since inception

**Commitment Information:**
- total_commitment: Total committed capital
- drawn_commitment: Total drawn capital
- unfunded_commitment: Remaining undrawn commitment
- ownership_percentage: Investor's ownership %

**3. SPECIAL HANDLING:**

For multi-column tables like this example:
```
                           Quarter to    Year to      Inception to   Partnership total
                           30 June 2025  30 June 2025 30 June 2025   Inception to
                           EUR           EUR          EUR            30 June 2025 EUR
Balance brought forward    112,617       139,117      -              -
Ending balance            71,595        71,595       71,595         3,253,279
```

- Column 1: Data labels
- Column 2: Current period (Quarter) - USE THIS for period data
- Column 3: Year-to-date - USE THIS for YTD data  
- Column 4: Inception-to-date - USE THIS for ITD data
- Column 5: Partnership totals - IGNORE THIS (not investor-specific)

**4. DATE EXTRACTION:**
From filename "Q2 2025" extract as "2025-06-30"
From "30 June 2025" extract as "2025-06-30"
From headers or text, find the exact statement date

**5. NUMBER PARSING:**
- Handle parentheses as negative: (14,217) = -14217
- Parse German format: 1.234,56 = 1234.56
- Parse US format: 1,234.56 = 1234.56
- Remove currency symbols: €71,595 = 71595

RETURN: Complete JSON object with all extracted data. Use null for missing fields.

Example output:
{{
  "doc_type": "capital_account_statement",
  "fund_name": "Oakley Capital Origin II-A SCSp",
  "investor_name": "Brainweb Investment GmbH",
  "as_of_date": "2025-06-30",
  "period_type": "QUARTERLY",
  "reporting_currency": "EUR",
  "beginning_balance": 112617,
  "ending_balance": 71595,
  "contributions_period": 0,
  "distributions_period": 0,
  "total_commitment": 5000000,
  "drawn_commitment": 300000,
  "unfunded_commitment": 4700000
}}"""
        
        return prompt
    
    def _ensure_required_fields(self, extracted_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """Ensure required fields are present with fallbacks."""
        
        # Ensure as_of_date is present
        if not extracted_data.get('as_of_date'):
            # Extract from filename as fallback
            quarter_match = re.search(r'Q([1-4])\s+(\d{4})', filename, re.IGNORECASE)
            if quarter_match:
                quarter, year = quarter_match.groups()
                quarter_ends = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
                extracted_data['as_of_date'] = f"{year}-{quarter_ends[quarter]}"
                logger.info(f"Fallback date from filename: {extracted_data['as_of_date']}")
        
        # Ensure currency is present
        if not extracted_data.get('reporting_currency'):
            # Look for EUR, USD, GBP in filename or text
            if 'EUR' in filename.upper():
                extracted_data['reporting_currency'] = 'EUR'
            elif 'USD' in filename.upper():
                extracted_data['reporting_currency'] = 'USD'
            else:
                extracted_data['reporting_currency'] = 'EUR'  # Default for European funds
        
        # Ensure doc_type is present
        if not extracted_data.get('doc_type'):
            if 'capital account' in filename.lower():
                extracted_data['doc_type'] = 'capital_account_statement'
            elif 'quarterly' in filename.lower():
                extracted_data['doc_type'] = 'quarterly_report'
            elif 'call' in filename.lower():
                extracted_data['doc_type'] = 'capital_call_notice'
            elif 'distribution' in filename.lower():
                extracted_data['doc_type'] = 'distribution_notice'
            else:
                extracted_data['doc_type'] = 'other'
        
        # Normalize numeric fields
        numeric_fields = [
            'beginning_balance', 'ending_balance', 'contributions_period', 'distributions_period',
            'realized_gain_loss_period', 'unrealized_gain_loss_period', 'management_fees_period',
            'partnership_expenses_period', 'total_commitment', 'drawn_commitment', 'unfunded_commitment',
            'contributions_ytd', 'distributions_ytd', 'contributions_itd', 'distributions_itd',
            'ownership_percentage'
        ]
        
        for field in numeric_fields:
            if field in extracted_data and extracted_data[field] is not None:
                try:
                    extracted_data[field] = float(extracted_data[field])
                except (ValueError, TypeError, AttributeError) as e:
                    logger.debug(f"Could not convert {field} to float: {extracted_data[field]} - {e}")
                    extracted_data[field] = None
        
        return extracted_data