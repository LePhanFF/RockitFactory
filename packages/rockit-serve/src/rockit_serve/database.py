"""Async SQLite database for user data.

This is intentionally separate from the research DuckDB.
Research data (trades, sessions, observations) lives in DuckDB and is read-only from the API.
User data (accounts, preferences, journal entries, bot keys) lives in SQLite.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from rockit_serve.config import USER_DB_URL

engine = create_async_engine(USER_DB_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields an async session."""
    async with async_session() as session:
        yield session
