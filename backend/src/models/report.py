"""
GeneratedReport model for storing analysis reports with citations and metadata.
Includes full-text search capabilities and audit trails.
"""
from sqlalchemy import (
    Column, String, DateTime, Text, Integer, 
    ForeignKey, Index, UniqueConstraint, JSON, Boolean
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.database.session import Base
from datetime import datetime
import uuid

class GeneratedReport(Base):
    """
    Persistent storage for AI-generated financial analysis reports.
    Links to user, ticker, and includes complete report + citations for auditability.
    """
    __tablename__ = "generated_reports"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Foreign key to user (CASCADE delete)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Financial data
    ticker = Column(String(20), nullable=False, index=True)
    company_name = Column(String(255), nullable=True)
    
    # Query & Report Content
    query = Column(String(500), nullable=False)  # Original user query
    
    # Structured report sections (JSONB for efficient querying in PostgreSQL)
    fundamental_report = Column(JSONB, nullable=True)  # e.g., {"analysis": "...", "score": 7.5}
    technical_report = Column(JSONB, nullable=True)
    sentiment_report = Column(JSONB, nullable=True)
    final_report = Column(Text, nullable=False)  # Full synthesized report
    
    # Citations & Sources (JSONB for fast retrieval)
    citations = Column(
        JSONB,
        default=list,
        nullable=False
    )  # [{"title": "...", "url": "...", "source": "...", "published_at": "..."}]
    
    # Metrics & Sentiment
    sentiment_score = Column(Integer, nullable=True)  # -100 to +100 scale
    bull_score = Column(Integer, nullable=True, default=0)  # 0-100
    bear_score = Column(Integer, nullable=True, default=0)  # 0-100
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Performance tracking
    generation_time_ms = Column(Integer, nullable=True)  # How long report took to generate
    is_cached = Column(Boolean, default=False)  # For cache hit tracking
    
    # Constraints
    __table_args__ = (
        Index('idx_report_ticker_created', 'ticker', 'created_at'),
        Index('idx_report_user_created', 'user_id', 'created_at'),
        Index('idx_report_sentiment_score', 'sentiment_score'),
    )
    
    def __repr__(self):
        return f"<GeneratedReport(id={self.id}, ticker={self.ticker}, user_id={self.user_id})>"
