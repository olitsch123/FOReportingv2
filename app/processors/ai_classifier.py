"""AI-powered document classifier using OpenAI."""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
import tiktoken
import openai

from app.config import load_settings
import os

settings = load_settings()
from app.database.models import DocumentType


class AIClassifier:
    """AI-powered document classifier and data extractor."""
    
    def __init__(self):
        """Initialize the AI classifier."""
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = settings.get("OPENAI_MODEL", "gpt-4-1106-preview")
        self.max_tokens = settings.get("MAX_TOKENS", 4000)
        self.temperature = settings.get("TEMPERATURE", 0.1)
        
        # Initialize tokenizer for text chunking
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def classify_and_extract(self, text: str, filename: str) -> Dict[str, Any]:
        """Classify document type and extract structured data."""
        try:
            # Truncate text if too long
            truncated_text = self._truncate_text(text, max_tokens=3000)
            
            # Create classification prompt
            prompt = self._create_classification_prompt(truncated_text, filename)
            
            # Call OpenAI API
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
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            # Parse response
            result = self._parse_response(response.choices[0].message.content)
            
            return result
            
        except Exception as e:
            return {
                'document_type': DocumentType.OTHER,
                'confidence_score': 0.0,
                'summary': f'Error in AI classification: {str(e)}',
                'error': str(e)
            }
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for document classification."""
        return """You are a financial document analysis expert specializing in private equity, venture capital, and investment fund reporting. Your task is to:

1. Classify the document type
2. Extract key financial data
3. Identify reporting periods
4. Summarize the document content

You must respond with a valid JSON object containing:
- document_type: one of [quarterly_report, annual_report, financial_statement, investment_report, portfolio_summary, transaction_data, benchmark_data, other]
- confidence_score: float between 0.0 and 1.0
- summary: brief description of the document content
- reporting_date: ISO date string if identifiable (YYYY-MM-DD)
- financial_metrics: object with extracted financial data
- fund_information: object with fund details if available

Be precise and conservative in your classifications. If uncertain, use "other" and lower confidence scores."""
    
    def _create_classification_prompt(self, text: str, filename: str) -> str:
        """Create the classification prompt."""
        return f"""Analyze this financial document and provide a structured analysis:

FILENAME: {filename}

DOCUMENT CONTENT:
{text}

Please analyze this document and return a JSON response with the following structure:
{{
    "document_type": "string (one of: quarterly_report, annual_report, financial_statement, investment_report, portfolio_summary, transaction_data, benchmark_data, other)",
    "confidence_score": "float (0.0 to 1.0)",
    "summary": "string (brief summary of document content)",
    "reporting_date": "string (ISO date YYYY-MM-DD if identifiable, null otherwise)",
    "financial_metrics": {{
        "nav": "float or null",
        "total_value": "float or null",
        "irr": "float or null",
        "moic": "float or null",
        "committed_capital": "float or null",
        "drawn_capital": "float or null",
        "distributed_capital": "float or null"
    }},
    "fund_information": {{
        "fund_name": "string or null",
        "fund_code": "string or null",
        "asset_class": "string or null",
        "vintage_year": "integer or null"
    }},
    "period_information": {{
        "period_type": "string (quarterly, annual, monthly, or null)",
        "quarter": "integer (1-4) or null",
        "year": "integer or null"
    }}
}}

Focus on extracting accurate financial data and identifying the document type based on its content and structure."""
    
    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limits."""
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        # Truncate tokens and decode back to text
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoding.decode(truncated_tokens)
        
        return truncated_text
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the AI response into structured data."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # Validate and clean the result
                return self._validate_and_clean_result(result)
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback parsing
            return self._fallback_parse(response_text)
    
    def _validate_and_clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the AI response result."""
        cleaned = {
            'document_type': DocumentType.OTHER,
            'confidence_score': 0.0,
            'summary': '',
            'reporting_date': None,
            'financial_metrics': {},
            'fund_information': {},
            'period_information': {}
        }
        
        # Validate document type
        doc_type = result.get('document_type', '').lower()
        valid_types = [e.value for e in DocumentType]
        if doc_type in valid_types:
            cleaned['document_type'] = DocumentType(doc_type)
        
        # Validate confidence score
        confidence = result.get('confidence_score', 0.0)
        if isinstance(confidence, (int, float)) and 0.0 <= confidence <= 1.0:
            cleaned['confidence_score'] = float(confidence)
        
        # Extract summary
        summary = result.get('summary', '')
        if isinstance(summary, str):
            cleaned['summary'] = summary[:1000]  # Limit length
        
        # Extract reporting date
        reporting_date = result.get('reporting_date')
        if reporting_date and isinstance(reporting_date, str):
            try:
                # Validate date format
                datetime.fromisoformat(reporting_date.replace('Z', '+00:00'))
                cleaned['reporting_date'] = reporting_date
            except ValueError:
                pass
        
        # Extract nested objects
        for key in ['financial_metrics', 'fund_information', 'period_information']:
            if key in result and isinstance(result[key], dict):
                cleaned[key] = result[key]
        
        return cleaned
    
    def _fallback_parse(self, response_text: str) -> Dict[str, Any]:
        """Fallback parsing when JSON parsing fails."""
        # Simple pattern matching for basic information
        result = {
            'document_type': DocumentType.OTHER,
            'confidence_score': 0.1,
            'summary': response_text[:200] if response_text else 'Unable to parse AI response',
            'reporting_date': None,
            'financial_metrics': {},
            'fund_information': {},
            'period_information': {}
        }
        
        # Try to extract document type from text
        text_lower = response_text.lower()
        if 'quarterly' in text_lower:
            result['document_type'] = DocumentType.QUARTERLY_REPORT
            result['confidence_score'] = 0.3
        elif 'annual' in text_lower:
            result['document_type'] = DocumentType.ANNUAL_REPORT
            result['confidence_score'] = 0.3
        elif 'financial statement' in text_lower:
            result['document_type'] = DocumentType.FINANCIAL_STATEMENT
            result['confidence_score'] = 0.3
        
        return result