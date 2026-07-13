"""The runtime-config endpoint the SPA uses to decide which sign-in to offer.

This is what stops a production deployment rendering a "Dev login" button that
would 404, and what lets one built image run in every environment.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_config_is_public(client: TestClient) -> None:
    # The login page must be able to read this before anyone is signed in.
    assert client.get("/api/config").status_code == 200


def test_config_reports_dev_login_and_google(client: TestClient) -> None:
    body = client.get("/api/config").json()
    assert body["dev_login"] is True  # test settings enable the bypass
    assert body["google_client_id"] == "test-client-id"


def test_production_shape_hides_dev_login(client: TestClient) -> None:
    """With DEV_LOGIN off and a real client id, only Google is offered."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        db_url="sqlite://",
        session_secret="test-secret",
        dev_login=False,
        google_client_id="prod-client-id.apps.googleusercontent.com",
    )
    body = client.get("/api/config").json()
    assert body["dev_login"] is False
    assert body["google_client_id"] == "prod-client-id.apps.googleusercontent.com"


def test_unconfigured_google_is_null_not_empty_string(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        db_url="sqlite://",
        session_secret="test-secret",
        dev_login=False,
        google_client_id="",
    )
    assert client.get("/api/config").json()["google_client_id"] is None


def test_config_leaks_no_secrets(client: TestClient) -> None:
    """Only the two public fields — never the session secret or TMDB key."""
    body = client.get("/api/config").json()
    assert set(body) == {"google_client_id", "dev_login"}
