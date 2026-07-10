"""M0 smoke test: the API is reachable and the SPA catch-all does not shadow it.

Verifies design risk #3 (route ordering): an /api route resolves to JSON even
though a catch-all route also exists for the SPA.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
