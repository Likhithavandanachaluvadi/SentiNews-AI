"""
SQLAlchemy ORM models for SentiNews AI.
All models inherit from Base and are auto-discovered by Alembic.
"""
from src.models.user import User
from src.models.report import GeneratedReport
from src.models.watchlist import Watchlist, WatchlistItem
from src.models.company_master import CompanyMaster

__all__ = [
    "User",
    "GeneratedReport",
    "Watchlist",
    "WatchlistItem",
    "CompanyMaster",
]
