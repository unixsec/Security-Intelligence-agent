"""Database connection and session management.

Uses `pool_pre_ping=True` so broken connections are discarded before use
(instead of surfacing as OperationalError on first query). Callers that
need bounded retries on transient outages should wrap their call in
`sia.common.resilience.resilient_call(db_breaker, ...)`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from sia.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.db.async_url,
            pool_size=settings.db.pool_size,
            pool_recycle=settings.db.pool_recycle,
            pool_pre_ping=True,              # SEC: detect stale connections
            echo=settings.debug,
            connect_args=settings.db.async_connect_args(),
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager variant for non-FastAPI code."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Convenience wrapper for CB-guarded ad-hoc queries.
# Prefer an explicit `resilient_call(db_breaker, ...)` at the call site for
# clarity — this exists for places that want a one-liner.
async def resilient_db_execute(fn, *args, **kwargs):
    """Execute `fn(session, *args)` in a CB-guarded, retryable transaction."""
    from sia.common.resilience import db_breaker, resilient_call

    async def _op():
        async with get_db_context() as session:
            return await fn(session, *args, **kwargs)

    return await resilient_call(db_breaker, _op)


async def init_db() -> None:
    """Create all tables (dev/test only).

    Importing sia.models eagerly registers every ORM class with Base.metadata
    so create_all sees the full schema even when called before the API routers
    (which also import model modules) are loaded.
    """
    import sia.models  # noqa: F401 — side-effect import to register metadata

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
