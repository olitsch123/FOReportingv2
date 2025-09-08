"""Unit tests for database models."""

import pytest
from datetime import datetime
from decimal import Decimal

from app.database.models import (
    Investor, Fund, Document, FinancialData,
    DocumentType, AssetClass, ProcessingStatus
)


class TestInvestor:
    """Test Investor model."""
    
    def test_investor_creation(self, test_db_session):
        """Test creating an investor."""
        investor = Investor(
            name="Test Investor",
            code="test_inv",
            description="Test description",
            folder_path="/test/path"
        )
        test_db_session.add(investor)
        test_db_session.commit()
        
        assert investor.id is not None
        assert investor.name == "Test Investor"
        assert investor.code == "test_inv"
        assert investor.created_at is not None
    
    def test_investor_unique_constraints(self, test_db_session):
        """Test investor unique constraints."""
        # Create first investor
        investor1 = Investor(
            name="Test Investor",
            code="test_inv",
            folder_path="/test/path1"
        )
        test_db_session.add(investor1)
        test_db_session.commit()
        
        # Try to create duplicate - should fail
        investor2 = Investor(
            name="Test Investor",  # Duplicate name
            code="different_code",
            folder_path="/test/path2"
        )
        test_db_session.add(investor2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            test_db_session.commit()


class TestFund:
    """Test Fund model."""
    
    def test_fund_creation(self, test_db_session, sample_investor):
        """Test creating a fund."""
        fund = Fund(
            name="Test Fund",
            code="TEST_FUND",
            asset_class=AssetClass.PRIVATE_EQUITY,
            vintage_year=2023,
            fund_size=100.0,
            currency="EUR",
            investor_id=sample_investor.id
        )
        test_db_session.add(fund)
        test_db_session.commit()
        
        assert fund.id is not None
        assert fund.name == "Test Fund"
        assert fund.asset_class == AssetClass.PRIVATE_EQUITY
        assert fund.investor == sample_investor
    
    def test_fund_relationships(self, test_db_session, sample_fund):
        """Test fund relationships."""
        assert sample_fund.investor is not None
        assert sample_fund.investor.name == "Test Investor"


class TestDocument:
    """Test Document model."""
    
    def test_document_creation(self, test_db_session, sample_investor, sample_fund):
        """Test creating a document."""
        document = Document(
            filename="test.pdf",
            file_path="/test/test.pdf",
            file_size=1024,
            file_hash="test_hash",
            mime_type="application/pdf",
            document_type=DocumentType.QUARTERLY_REPORT,
            processing_status=ProcessingStatus.PENDING,
            investor_id=sample_investor.id,
            fund_id=sample_fund.id
        )
        test_db_session.add(document)
        test_db_session.commit()
        
        assert document.id is not None
        assert document.filename == "test.pdf"
        assert document.document_type == DocumentType.QUARTERLY_REPORT
        assert document.processing_status == ProcessingStatus.PENDING
    
    def test_document_relationships(self, test_db_session, sample_document):
        """Test document relationships."""
        assert sample_document.investor is not None
        assert sample_document.fund is not None
        assert sample_document.investor.name == "Test Investor"


class TestFinancialData:
    """Test FinancialData model."""
    
    def test_financial_data_creation(self, test_db_session, sample_fund):
        """Test creating financial data."""
        financial_data = FinancialData(
            fund_id=sample_fund.id,
            reporting_date=datetime(2023, 6, 30).date(),
            period_type="quarterly",
            nav=Decimal("1000000.00"),
            total_value=Decimal("1200000.00"),
            irr=Decimal("15.5"),
            moic=Decimal("1.2"),
            currency="EUR"
        )
        test_db_session.add(financial_data)
        test_db_session.commit()
        
        assert financial_data.id is not None
        assert financial_data.nav == Decimal("1000000.00")
        assert financial_data.fund == sample_fund
    
    def test_financial_data_calculations(self, test_db_session, sample_fund):
        """Test financial data calculations."""
        financial_data = FinancialData(
            fund_id=sample_fund.id,
            reporting_date=datetime(2023, 6, 30).date(),
            committed_capital=Decimal("5000000.00"),
            drawn_capital=Decimal("3000000.00"),
            distributed_capital=Decimal("1000000.00"),
            currency="EUR"
        )
        test_db_session.add(financial_data)
        test_db_session.commit()
        
        # Test calculated fields
        unfunded = financial_data.committed_capital - financial_data.drawn_capital
        assert unfunded == Decimal("2000000.00")