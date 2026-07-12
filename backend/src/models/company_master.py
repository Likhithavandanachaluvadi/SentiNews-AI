from sqlalchemy import Column, String, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from src.database.session import Base


class CompanyMaster(Base):
    __tablename__ = "company_master"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    symbol = Column(String(20), nullable=False, unique=True, index=True)

    company_name = Column(String(255), nullable=False)

    industry = Column(String(255), nullable=True, index=True)

    sector = Column(String(255), nullable=True, index=True)

    market_cap = Column(BigInteger, nullable=True)

    last_updated = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )