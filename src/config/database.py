"""Async SQLAlchemy engine and session factory. No pipeline logic."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings


def get_engine():
    """Create or return async engine for settings.database_url."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
    )


def get_session_factory():
    """Return async session factory bound to the engine."""
    engine = get_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for a single async session. Use for all DB access."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
