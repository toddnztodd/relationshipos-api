"""Async SQLAlchemy database engine and session management.

Supports both PostgreSQL (via asyncpg) and SQLite (via aiosqlite).
The driver is auto-detected from the DATABASE_URL environment variable.
"""

import logging
import ssl
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Resolve the async-compatible URL
_db_url = settings.async_database_url

# For SQLite: ensure the data directory exists
if "sqlite" in _db_url:
    _db_path = _db_url.split("///")[-1]
    if _db_path and not _db_path.startswith(":"):
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

# Engine kwargs differ between SQLite and PostgreSQL
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "future": True,
}

if settings.is_postgres:
    # Use NullPool for serverless/free-tier PostgreSQL to avoid connection limits
    _engine_kwargs["poolclass"] = NullPool

    # Set up SSL for Neon and other cloud PostgreSQL providers
    if "sslmode=require" in settings.DATABASE_URL:
        # Create an SSL context that doesn't verify certificates (required for Neon pooler)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _engine_kwargs["connect_args"] = {"ssl": ssl_context}
        # Remove sslmode from URL since we handle it via connect_args
        _db_url = _db_url.replace("?sslmode=require", "").replace("&sslmode=require", "")

    logger.info("Using PostgreSQL database (persistent)")
else:
    logger.info("Using SQLite database (ephemeral on Render)")

engine = create_async_engine(_db_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
