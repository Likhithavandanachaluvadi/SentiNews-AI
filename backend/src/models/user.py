"""
User model with production security: password hashing, JWT support, audit timestamps.
"""
from sqlalchemy import Column, String, DateTime, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from src.database.session import Base
from datetime import datetime
import uuid

class User(Base):
    """
    User account model with security-first design.
    - UUID primary key (prevents enumeration attacks)
    - Hashed passwords (bcrypt)
    - Audit timestamps (created_at, updated_at, last_login)
    - Email uniqueness constraint
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Auth fields
    email = Column(String(255), nullable=False, index=True)
    username = Column(String(100), nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)  # bcrypt hash
    
    # Profile & Status
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_premium = Column(Boolean, default=False)  # Premium tier for higher rate limits
    
    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('email', name='uq_user_email'),
        UniqueConstraint('username', name='uq_user_username'),
        Index('idx_user_is_active', 'is_active'),
        Index('idx_user_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, is_active={self.is_active})>"
