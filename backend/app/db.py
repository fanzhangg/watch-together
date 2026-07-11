"""Database engine, session factory, and the request-scoped session dependency.

Sync SQLAlchemy 2.0 (not async) — the right call for a two-user app. The engine
is created lazily on first use so the app can be imported without a database
(e.g. the health-check smoke test).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _init() -> sessionmaker[Session]:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        settings = get_settings()
        if settings.is_sqlite:
            # SQLite (local dev / tests) doesn't take the Postgres pool args.
            _engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False},
                future=True,
            )
        else:
            # Postgres (Neon): pool_pre_ping guards against idle connections
            # being closed on autosuspend; a small pool + recycle keeps us well
            # under serverless connection limits.
            _engine = create_engine(
                settings.database_url,
                pool_pre_ping=True,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_recycle=settings.db_pool_recycle_seconds,
                future=True,
            )
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, expire_on_commit=False
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is closed after the request."""
    session = _init()()
    try:
        yield session
    finally:
        session.close()
