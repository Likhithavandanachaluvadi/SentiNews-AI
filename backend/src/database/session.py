"""
Async SQLAlchemy session factory for production database operations.
Provides thread-safe, connection-pooled async database access.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

# SQLAlchemy ORM Base
Base = declarative_base()

# Async engine — uses AsyncAdaptedQueuePool automatically (no poolclass override needed)
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",  # Log SQL only in dev
    future=True,
    pool_pre_ping=True,  # Validate connections before use (prevent stale connections)
    pool_size=20,        # Number of connections to maintain in pool
    max_overflow=10,     # Additional connections allowed beyond pool_size
    pool_recycle=3600,   # Recycle connections after 1 hour
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

async def get_session() -> AsyncSession:
    """
    Dependency injection for async sessions.
    Usage in FastAPI:
        async def endpoint(session: AsyncSession = Depends(get_session)):
            # Use session
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# async def init_db():
#     """Initialize database tables (run once during startup)."""
#     # Import all models to ensure they are registered on Base metadata
#     import src.models
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     logger.info("Database tables initialized")
async def init_db():
    """Initialize database tables (run once during startup)."""

    import src.models

    print("TABLES =", Base.metadata.tables.keys())

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables initialized")

async def close_db():
    """Close database connection pool (run on shutdown)."""
    await engine.dispose()
    logger.info("Database connections closed")
