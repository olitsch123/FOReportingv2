"""Unit tests for PE document extractors."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.pe_docs.extractors.base import ExtractionResult, ExtractionMethod
from app.pe_docs.extractors.capital_account import CapitalAccountExtractor
from app.pe_docs.extractors.ai_field_matcher import AIFieldMatcher


class TestCapitalAccountExtractor:
    """Test CapitalAccountExtractor."""
    
    def test_extractor_initialization(self):
        """Test extractor initializes correctly."""
        extractor = CapitalAccountExtractor()
        assert extractor is not None
        assert hasattr(extractor, 'extract')
    
    def test_extract_balance_amounts(self):
        """Test extraction of balance amounts from text."""
        extractor = CapitalAccountExtractor()
        
        text = """
        Beginning Balance: €1,000,000
        Ending Balance: €1,500,000
        Contributions: €750,000
        Distributions: €250,000
        """
        
        result = extractor._extract_balance_amounts(text)
        
        assert result['beginning_balance'] == 1000000.0
        assert result['ending_balance'] == 1500000.0
        assert result['contributions_period'] == 750000.0
        assert result['distributions_period'] == 250000.0
    
    def test_extract_fund_info(self):
        """Test extraction of fund information."""
        extractor = CapitalAccountExtractor()
        
        text = """
        Fund: Test Private Equity Fund LP
        Period: Q2 2023
        As of: June 30, 2023
        """
        
        result = extractor._extract_fund_info(text)
        
        assert 'Test Private Equity Fund' in result['fund_name']
        assert result['period_label'] == 'Q2 2023'
    
    def test_parse_currency_values(self):
        """Test currency value parsing."""
        extractor = CapitalAccountExtractor()
        
        test_cases = [
            ("€1,000,000", 1000000.0),
            ("$2,500,000.50", 2500000.50),
            ("1.234.567,89", 1234567.89),  # German format
            ("(500,000)", -500000.0),  # Negative in parentheses
        ]
        
        for text, expected in test_cases:
            result = extractor._parse_currency_value(text)
            assert result == expected
    
    def test_extract_with_mock_text(self, sample_pdf_content):
        """Test full extraction with sample content."""
        extractor = CapitalAccountExtractor()
        
        with patch.object(extractor, '_classify_document') as mock_classify:
            mock_classify.return_value = ("capital_account_statement", 0.95)
            
            result = extractor.extract(sample_pdf_content, "test.pdf")
            
            assert isinstance(result, ExtractionResult)
            assert result.extraction_method == ExtractionMethod.REGEX_PATTERN
            assert result.confidence_score > 0.5
            assert 'fund_name' in result.extracted_data


class TestAIFieldMatcher:
    """Test AIFieldMatcher."""
    
    def test_field_matcher_initialization(self):
        """Test field matcher initializes correctly."""
        matcher = AIFieldMatcher()
        assert matcher is not None
        assert hasattr(matcher, 'match_fields')
    
    def test_validate_currency(self):
        """Test currency validation."""
        matcher = AIFieldMatcher()
        
        test_cases = [
            (1000000, 1000000.0),
            ("1,500,000", 1500000.0),
            ("€2,000,000", 2000000.0),
            ("invalid", None),
            (None, None),
        ]
        
        for input_val, expected in test_cases:
            result = matcher._validate_currency(input_val)
            assert result == expected
    
    def test_validate_date(self):
        """Test date validation."""
        matcher = AIFieldMatcher()
        
        test_cases = [
            ("2023-06-30", "2023-06-30"),
            ("June 30, 2023", "2023-06-30"),
            ("30/06/2023", "2023-06-30"),
            ("Q2 2023", None),  # Should fail for quarter format
            ("invalid", None),
        ]
        
        for input_val, expected in test_cases:
            result = matcher._validate_date(input_val)
            if expected:
                assert result == expected
            else:
                assert result is None
    
    @patch('openai.OpenAI')
    def test_match_fields_with_mock_openai(self, mock_openai, sample_extraction_result):
        """Test field matching with mocked OpenAI."""
        # Setup mock
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content='{"fund_name": "Test Fund"}'))]
        )
        
        matcher = AIFieldMatcher()
        
        text = "Sample document text"
        target_fields = ["fund_name", "beginning_balance"]
        
        result = matcher.match_fields(text, target_fields)
        
        assert isinstance(result, dict)
        assert 'fund_name' in result
    
    def test_validate_extracted_data(self, sample_extraction_result):
        """Test validation of extracted data."""
        matcher = AIFieldMatcher()
        
        # Test with valid data
        validated = matcher._validate_extracted_data(sample_extraction_result)
        
        assert 'beginning_balance' in validated
        assert isinstance(validated['beginning_balance'], float)
        assert validated['beginning_balance'] == 1000000.0
    
    def test_handle_extraction_errors(self):
        """Test error handling in extraction."""
        matcher = AIFieldMatcher()
        
        # Test with invalid JSON response
        with patch.object(matcher, '_call_openai') as mock_call:
            mock_call.return_value = "invalid json"
            
            result = matcher.match_fields("test text", ["fund_name"])
            
            # Should return empty dict on error
            assert result == {}


@pytest.fixture
def mock_extraction_result():
    """Mock extraction result for testing."""
    return ExtractionResult(
        extracted_data={
            "fund_name": "Test Fund",
            "beginning_balance": 1000000.0,
            "ending_balance": 1500000.0
        },
        confidence_score=0.85,
        extraction_method=ExtractionMethod.AI_EXTRACTION,
        processing_time=1.5,
        metadata={"source": "test"}
    )