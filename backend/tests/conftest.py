"""Shared pytest fixtures.

M0 provides only the API ``client`` (no database needed for the health check).
From M2 onward a DB fixture is added here: point ``TEST_DATABASE_URL`` at a
throwaway Neon branch (or local Docker Postgres), create the schema, and wrap
each test in a transaction that rolls back — see docs/design.md section 11.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
