"""Shared pytest fixtures.

By default tests run on a fresh in-memory SQLite database (fast, zero install).
Set ``TEST_DATABASE_URL`` (e.g. a throwaway Neon branch) to run the exact same
tests against real Postgres for prod-accurate constraint behavior — recommended
from M2/M3 on. Schema is created via ``Base.metadata.create_all`` and dropped
after each test.

Settings are overridden so DEV_LOGIN is on and secrets are deterministic.
Helpers create users and return TestClients authenticated as them.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import Base, enable_sqlite_fk, get_db
from app.main import app
from app.models import User  # noqa: F401  (register tables on Base.metadata)
from app.security import issue_session

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        db_url="sqlite://",
        session_secret="test-secret",
        google_client_id="test-client-id",
        dev_login=True,
        session_cookie_secure=False,
    )


def _make_engine() -> Engine:
    if TEST_DATABASE_URL:
        url = Settings(db_url=TEST_DATABASE_URL).database_url  # normalize driver
        return create_engine(url, pool_pre_ping=True)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared connection for the in-memory DB
    )
    enable_sqlite_fk(engine)
    return engine


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = _make_engine()
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client_factory(
    settings: Settings, db_session: Session
) -> Iterator[Callable[..., TestClient]]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = override_get_db

    def make(user: User | None = None) -> TestClient:
        c = TestClient(app)
        if user is not None:
            c.cookies.set(
                settings.session_cookie_name, issue_session(settings, str(user.id))
            )
        return c

    try:
        yield make
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(client_factory: Callable[..., TestClient]) -> TestClient:
    """An unauthenticated client (used by the auth tests)."""
    return client_factory()


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _make(email: str, name: str | None = None, google_sub: str | None = None) -> User:
        user = User(email=email, display_name=name, google_sub=google_sub)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make
