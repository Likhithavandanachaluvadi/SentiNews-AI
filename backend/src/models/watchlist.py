"""
Watchlist models for user portfolio tracking.
Users can create multiple watchlists with multiple tickers.
"""
from sqlalchemy import (
    Column, String, DateTime, Integer, 
    ForeignKey, Index, UniqueConstraint, Float, Text
)
from sqlalchemy.dialects.postgresql import UUID
from src.database.session import Base
from datetime import datetime
import uuid

class Watchlist(Base):
    """
    User's watchlist collection (e.g., "Tech Stocks", "Growth Portfolio").
    """
    __tablename__ = "watchlists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    name = Column(String(100), nullable=False)  # e.g., "My Tech Watch"
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_watchlist_user_name'),
        Index('idx_watchlist_user', 'user_id'),
    )
    
    def __repr__(self):
        return f"<Watchlist(id={self.id}, name={self.name}, user_id={self.user_id})>"

class WatchlistItem(Base):
    """
    Individual ticker in a watchlist with performance tracking.
    """
    __tablename__ = "watchlist_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    watchlist_id = Column(UUID(as_uuid=True), ForeignKey('watchlists.id', ondelete='CASCADE'), nullable=False, index=True)
    
    ticker = Column(String(20), nullable=False, index=True)
    company_name = Column(String(255), nullable=True)
    
    # Price tracking
    entry_price = Column(Float, nullable=True)  # Price when added to watchlist
    current_price = Column(Float, nullable=True)
    last_price_update = Column(DateTime, nullable=True)
    
    # Performance metrics (cached for fast display)
    price_change_percent = Column(Float, nullable=True)  # % change from entry
    
    # Sentiment cache
    latest_sentiment_score = Column(Integer, nullable=True)  # -100 to +100
    latest_report_id = Column(UUID(as_uuid=True), ForeignKey('generated_reports.id', ondelete='SET NULL'), nullable=True)
    
    # Tracking
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('watchlist_id', 'ticker', name='uq_watchlist_item_ticker'),
        Index('idx_watchlist_item_ticker', 'ticker'),
        Index('idx_watchlist_item_sentiment', 'latest_sentiment_score'),
    )
    
    def __repr__(self):
        return f"<WatchlistItem(ticker={self.ticker}, watchlist_id={self.watchlist_id})>"
