"""Shared pytest fixtures.

Tests run against a fresh in-memory SQLite database per test (fast, isolated,
zero install). The model types are portable, so the same schema is created via
``Base.metadata.create_all``. Production/Neon uses Postgres; when a real
Postgres is wired up (M2/M3) point the engine here at it instead.

Settings are overridden so DEV_LOGIN is on and secrets are deterministic.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, get_db
from app.main import app
from app.models import User  # noqa: F401  (register the table on Base.metadata)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        db_url="sqlite://",
        session_secret="test-secret",
        google_client_id="test-client-id",
        dev_login=True,
        session_cookie_secure=False,
    )


@pytest.fixture
def db_session(settings: Settings) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection for the in-memory DB
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(settings: Settings, db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
