"""Database models for FOReporting v2."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class DocumentType(str, Enum):
    """Document type enumeration."""
    QUARTERLY_REPORT = "quarterly_report"
    ANNUAL_REPORT = "annual_report"
    FINANCIAL_STATEMENT = "financial_statement"
    INVESTMENT_REPORT = "investment_report"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    TRANSACTION_DATA = "transaction_data"
    BENCHMARK_DATA = "benchmark_data"
    OTHER = "other"


class AssetClass(str, Enum):
    """Asset class enumeration."""
    PRIVATE_EQUITY = "private_equity"
    VENTURE_CAPITAL = "venture_capital"
    REAL_ESTATE = "real_estate"
    INFRASTRUCTURE = "infrastructure"
    CREDIT = "credit"
    HEDGE_FUNDS = "hedge_funds"
    PUBLIC_EQUITY = "public_equity"
    FIXED_INCOME = "fixed_income"
    COMMODITIES = "commodities"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Investor(Base):
    """Investor/entity model."""
    __tablename__ = "investors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)  # e.g., "brainweb", "pecunalta"
    description = Column(Text)
    folder_path = Column(String(500), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    documents = relationship("Document", back_populates="investor")
    funds = relationship("Fund", back_populates="investor")


class Fund(Base):
    """Fund model."""
    __tablename__ = "funds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=False)
    asset_class = Column(String(50), nullable=False)  # AssetClass enum
    vintage_year = Column(Integer)
    fund_size = Column(Float)  # in millions
    currency = Column(String(3), default="EUR")
    
    # Foreign keys
    investor_id = Column(UUID(as_uuid=True), ForeignKey("investors.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    investor = relationship("Investor", back_populates="funds")
    documents = relationship("Document", back_populates="fund")
    financial_data = relationship("FinancialData", back_populates="fund")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("investor_id", "code", name="uq_investor_fund_code"),
        Index("ix_funds_asset_class", "asset_class"),
        Index("ix_funds_vintage_year", "vintage_year"),
    )


class Document(Base):
    """Document model."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer)  # in bytes
    file_hash = Column(String(64))  # SHA-256 hash for deduplication
    mime_type = Column(String(100))
    
    # Classification
    document_type = Column(String(50), nullable=False)  # DocumentType enum
    confidence_score = Column(Float)  # AI classification confidence
    
    # Processing
    processing_status = Column(String(20), default=ProcessingStatus.PENDING)
    processing_error = Column(Text)
    processed_at = Column(DateTime(timezone=True))
    
    # Content
    raw_text = Column(Text)
    structured_data = Column(JSON)  # Extracted structured data
    summary = Column(Text)
    
    # Metadata
    reporting_date = Column(DateTime(timezone=True))  # Date the document reports on
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Foreign keys
    investor_id = Column(UUID(as_uuid=True), ForeignKey("investors.id"), nullable=False)
    fund_id = Column(UUID(as_uuid=True), ForeignKey("funds.id"))
    
    # Relationships
    investor = relationship("Investor", back_populates="documents")
    fund = relationship("Fund", back_populates="documents")
    financial_data = relationship("FinancialData", back_populates="document")
    embeddings = relationship("DocumentEmbedding", back_populates="document")
    
    # Constraints
    __table_args__ = (
        Index("ix_documents_file_hash", "file_hash"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_processing_status", "processing_status"),
        Index("ix_documents_reporting_date", "reporting_date"),
        UniqueConstraint("file_hash", name="uq_document_file_hash"),
    )


class DocumentEmbedding(Base):
    """Document embeddings for vector search."""
    __tablename__ = "document_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    
    # Vector embedding is stored in ChromaDB, this is just metadata
    embedding_id = Column(String(100))  # ChromaDB document ID
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="embeddings")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        Index("ix_embeddings_document_id", "document_id"),
    )


class FinancialData(Base):
    """Financial data extracted from documents."""
    __tablename__ = "financial_data"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Time series data
    reporting_date = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20))  # "quarterly", "annual", "monthly"
    
    # Financial metrics
    nav = Column(Float)  # Net Asset Value
    nav_per_share = Column(Float)
    total_value = Column(Float)
    committed_capital = Column(Float)
    drawn_capital = Column(Float)
    distributed_capital = Column(Float)
    unrealized_value = Column(Float)
    realized_value = Column(Float)
    
    # Performance metrics
    irr = Column(Float)  # Internal Rate of Return
    moic = Column(Float)  # Multiple of Invested Capital
    dpi = Column(Float)  # Distributions to Paid-in Capital
    rvpi = Column(Float)  # Residual Value to Paid-in Capital
    tvpi = Column(Float)  # Total Value to Paid-in Capital
    
    # Additional metrics (JSON for flexibility)
    additional_metrics = Column(JSON)
    
    # Currency
    currency = Column(String(3), default="EUR")
    
    # Foreign keys
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    fund_id = Column(UUID(as_uuid=True), ForeignKey("funds.id"), nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="financial_data")
    fund = relationship("Fund", back_populates="financial_data")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("fund_id", "reporting_date", "period_type", name="uq_fund_period_data"),
        Index("ix_financial_data_reporting_date", "reporting_date"),
        Index("ix_financial_data_fund_id", "fund_id"),
    )


class ChatSession(Base):
    """Chat session model for conversational interface."""
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_name = Column(String(255))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    """Chat message model."""
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    
    # Message content
    message_type = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    
    # Context
    context_documents = Column(JSON)  # List of document IDs used for context
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    # Constraints
    __table_args__ = (
        Index("ix_chat_messages_session_id", "session_id"),
        Index("ix_chat_messages_created_at", "created_at"),
    )