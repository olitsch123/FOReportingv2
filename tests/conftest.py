"""Pytest configuration and shared fixtures."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import Mock

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import Investor, Fund, Document


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_engine():
    """Create a test database engine using SQLite in memory."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session with proper cleanup."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    
    # Start a transaction
    transaction = session.begin()
    
    try:
        yield session
    finally:
        # Rollback the transaction to clean up
        session.rollback()
        session.close()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = Mock(
        choices=[
            Mock(
                message=Mock(
                    content='{"test": "data"}'
                )
            )
        ]
    )
    return mock_client


@pytest.fixture
def sample_investor(test_db_session) -> Investor:
    """Create a sample investor for testing."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    
    investor = Investor(
        name=f"Test Investor {unique_id}",
        code=f"test_investor_{unique_id}",
        description="Test investor for unit tests",
        folder_path="/test/path"
    )
    test_db_session.add(investor)
    test_db_session.commit()
    test_db_session.refresh(investor)
    return investor


@pytest.fixture
def sample_fund(test_db_session, sample_investor) -> Fund:
    """Create a sample fund for testing."""
    fund = Fund(
        name="Test Fund",
        code="TEST_FUND",
        asset_class="private_equity",
        vintage_year=2023,
        fund_size=100.0,
        currency="EUR",
        investor_id=sample_investor.id
    )
    test_db_session.add(fund)
    test_db_session.commit()
    test_db_session.refresh(fund)
    return fund


@pytest.fixture
def sample_document(test_db_session, sample_investor, sample_fund) -> Document:
    """Create a sample document for testing."""
    document = Document(
        filename="test_document.pdf",
        file_path="/test/path/test_document.pdf",
        file_size=1024,
        file_hash="test_hash",
        mime_type="application/pdf",
        document_type="quarterly_report",
        investor_id=sample_investor.id,
        fund_id=sample_fund.id
    )
    test_db_session.add(document)
    test_db_session.commit()
    test_db_session.refresh(document)
    return document


@pytest.fixture
def temp_test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test file content")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return {
        "DATABASE_URL": "sqlite:///:memory:",
        "OPENAI_API_KEY": "test_key",
        "OPENAI_VECTOR_STORE_ID": "test_store_id",
        "INVESTOR1_PATH": "/test/investor1",
        "INVESTOR2_PATH": "/test/investor2",
        "CHROMA_DIR": "/test/chroma",
        "DEPLOYMENT_MODE": "test"
    }


@pytest.fixture
def sample_pdf_content():
    """Sample PDF text content for testing - using actual test document."""
    return """CAPITAL ACCOUNT STATEMENT

Fund Name: Astorg VII
Fund Manager: Astorg Partners
Investor: BrainWeb Investment GmbH
Investor ID: BWI-001

Statement Date: December 31, 2023
Period: Q4 2023

CAPITAL ACCOUNT SUMMARY

Beginning Balance (October 1, 2023):             $35,000,000.00

ACTIVITY DURING PERIOD

Capital Contributions:
  Capital Call #12 (November 15, 2023)           $5,000,000.00
  Total Contributions This Period                $5,000,000.00

Distributions:
  Distribution - Return of Capital               ($2,000,000.00)
  Distribution - Realized Gains                  ($1,500,000.00)
  Distribution - Income                            ($500,000.00)
  Total Distributions This Period                ($4,000,000.00)

Management Fees:
  Q4 2023 Management Fee (0.5%)                   ($250,000.00)

Ending Balance (December 31, 2023):             $40,700,000.00

COMMITMENT INFORMATION

Total Commitment:                                $50,000,000.00
Drawn Commitment:                                $35,000,000.00
Unfunded Commitment:                             $15,000,000.00

Multiple on Invested Capital (MOIC):                     1.68x
Internal Rate of Return (IRR):                          18.5%
"""


@pytest.fixture
def sample_extraction_result():
    """Sample extraction result for testing - based on actual test document."""
    return {
        "fund_name": "Astorg VII",
        "fund_manager": "Astorg Partners",
        "investor_name": "BrainWeb Investment GmbH",
        "period_label": "Q4 2023",
        "beginning_balance": 35000000.0,
        "ending_balance": 40700000.0,
        "contributions_period": 5000000.0,
        "distributions_period": 4000000.0,
        "management_fees_period": 250000.0,
        "total_commitment": 50000000.0,
        "drawn_commitment": 35000000.0,
        "unfunded_commitment": 15000000.0,
        "moic": 1.68,
        "irr": 18.5,
        "as_of_date": "2023-12-31"
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")