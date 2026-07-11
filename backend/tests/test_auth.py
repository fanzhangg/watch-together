"""M1 auth integration tests.

Covers: /me gates on the session cookie (401 vs 200), dev-login issues a working
session, logout clears it, and the Google path upserts a user (verification
mocked so no network).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_google import GoogleIdentity
from app.config import Settings, get_settings
from app.main import app
from app.models import User


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_dev_login_then_me(client: TestClient) -> None:
    login = client.post("/api/auth/dev-login")
    assert login.status_code == 200
    body = login.json()
    assert body["email"] == "dev@local"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_logout_clears_session(client: TestClient) -> None:
    client.post("/api/auth/dev-login")
    assert client.get("/api/auth/me").status_code == 200

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_dev_login_disabled_returns_404(client: TestClient) -> None:
    # Re-point settings so DEV_LOGIN is off for this request.
    app.dependency_overrides[get_settings] = lambda: Settings(
        db_url="sqlite://", session_secret="test-secret", dev_login=False
    )
    resp = client.post("/api/auth/dev-login")
    assert resp.status_code == 404


def test_google_login_upserts_user(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_verify(credential: str, client_id: str) -> GoogleIdentity:
        assert credential == "fake-google-jwt"
        return GoogleIdentity(
            sub="google-123",
            email="alice@example.com",
            name="Alice",
            picture="https://img/alice.png",
        )

    monkeypatch.setattr("app.routers.auth.verify_google_token", fake_verify)

    resp = client.post("/api/auth/google", json={"credential": "fake-google-jwt"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"

    # Session works, and the user was persisted.
    assert client.get("/api/auth/me").status_code == 200
    user = db_session.execute(
        select(User).where(User.google_sub == "google-123")
    ).scalar_one()
    assert user.display_name == "Alice"


def test_google_login_invalid_token_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_verify(credential: str, client_id: str) -> GoogleIdentity:
        raise ValueError("invalid token")

    monkeypatch.setattr("app.routers.auth.verify_google_token", fake_verify)

    resp = client.post("/api/auth/google", json={"credential": "bad"})
    assert resp.status_code == 401
