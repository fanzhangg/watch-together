"""M3 tests: TMDB search proxy + movie item lifecycle.

TMDB is mocked throughout — no network and no API key needed. Covers the
stateful bit that actually has logic (status <-> watched_at) and the duplicate
add being idempotent rather than a 500.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from app.tmdb import Movie, TMDBError, TMDBNotFound

MATRIX = Movie(
    tmdb_id=603,
    title="The Matrix",
    release_year=1999,
    poster_path="/matrix.jpg",
    overview="A hacker learns the truth.",
)


@pytest.fixture
def alice(make_user: Callable[..., User]) -> User:
    return make_user("alice@example.com", "Alice")


@pytest.fixture
def bob(make_user: Callable[..., User]) -> User:
    return make_user("bob@example.com", "Bob")


@pytest.fixture
def mock_tmdb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.items.get_movie", lambda key, tmdb_id: MATRIX)
    monkeypatch.setattr("app.routers.tmdb.search_movies", lambda key, q: [MATRIX])


def _new_list(client: TestClient, name: str = "Date night") -> str:
    return client.post("/api/lists", json={"name": name}).json()["id"]


def test_search_returns_trimmed_results(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    resp = client_factory(alice).get("/api/tmdb/search", params={"q": "matrix"})
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "tmdb_id": 603,
            "title": "The Matrix",
            "release_year": 1999,
            "poster_path": "/matrix.jpg",
            "overview": "A hacker learns the truth.",
        }
    ]


def test_search_requires_auth(client_factory: Callable[..., TestClient]) -> None:
    assert client_factory().get("/api/tmdb/search", params={"q": "x"}).status_code == 401


def test_add_item_snapshots_metadata(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)

    added = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603})
    assert added.status_code == 201
    body = added.json()
    assert body["title"] == "The Matrix"
    assert body["release_year"] == 1999
    assert body["status"] == "want_to_watch"
    assert body["watched_at"] is None
    assert body["added_by"] == str(alice.id)

    listed = ca.get(f"/api/lists/{lid}/items").json()
    assert [i["tmdb_id"] for i in listed] == [603]


def test_status_toggle_sets_and_clears_watched_at(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    watched = ca.patch(f"/api/lists/{lid}/items/{iid}", json={"status": "watched"})
    assert watched.status_code == 200
    assert watched.json()["status"] == "watched"
    assert watched.json()["watched_at"] is not None

    # Toggling back clears watched_at.
    unwatched = ca.patch(
        f"/api/lists/{lid}/items/{iid}", json={"status": "want_to_watch"}
    )
    assert unwatched.json()["status"] == "want_to_watch"
    assert unwatched.json()["watched_at"] is None


def test_duplicate_add_is_idempotent(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)

    first = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603})
    second = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603})

    assert first.status_code == 201
    assert second.status_code == 200  # existing row returned, NOT a 500
    assert second.json()["id"] == first.json()["id"]
    assert len(ca.get(f"/api/lists/{lid}/items").json()) == 1


def test_duplicate_add_does_not_call_tmdb(
    client_factory: Callable[..., TestClient],
    alice: User,
    mock_tmdb: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A movie already in the list needs no metadata, so it must not hit TMDB.

    Regression: the existence check used to run *after* the TMDB fetch, so a
    flaky TMDB turned a harmless duplicate add into a 502.
    """
    ca = client_factory(alice)
    lid = _new_list(ca)
    first = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603})
    assert first.status_code == 201

    # Now make TMDB completely unavailable.
    def boom(key: str, tmdb_id: int) -> Movie:
        raise TMDBError("TMDB is down")

    monkeypatch.setattr("app.routers.items.get_movie", boom)

    second = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603})
    assert second.status_code == 200  # still fine — no TMDB call needed
    assert second.json()["id"] == first.json()["id"]


def test_delete_item(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    assert ca.delete(f"/api/lists/{lid}/items/{iid}").status_code == 204
    assert ca.get(f"/api/lists/{lid}/items").json() == []
    assert ca.delete(f"/api/lists/{lid}/items/{iid}").status_code == 404


def test_stranger_cannot_touch_items(
    client_factory: Callable[..., TestClient], alice: User, bob: User, mock_tmdb: None
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    assert cb.get(f"/api/lists/{lid}/items").status_code == 403
    assert cb.post(f"/api/lists/{lid}/items", json={"tmdb_id": 1}).status_code == 403
    assert (
        cb.patch(f"/api/lists/{lid}/items/{iid}", json={"status": "watched"}).status_code
        == 403
    )
    assert cb.delete(f"/api/lists/{lid}/items/{iid}").status_code == 403


def test_unknown_tmdb_id_maps_to_404_not_502(
    client_factory: Callable[..., TestClient],
    alice: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Asking for a movie TMDB doesn't have is a caller mistake, not a gateway
    failure — it must be a 404, not a 502."""

    def not_found(key: str, tmdb_id: int) -> Movie:
        raise TMDBNotFound("no such movie")

    monkeypatch.setattr("app.routers.items.get_movie", not_found)

    ca = client_factory(alice)
    lid = _new_list(ca)
    resp = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 99999999})
    assert resp.status_code == 404


def test_add_item_documents_both_200_and_201(
    client_factory: Callable[..., TestClient],
) -> None:
    """Swagger should show 201 (added) and 200 (already present), not just 200."""
    schema = client_factory().get("/openapi.json").json()
    responses = schema["paths"]["/api/lists/{list_id}/items"]["post"]["responses"]
    assert "201" in responses
    assert "200" in responses
    assert "422" in responses  # validation errors are documented by FastAPI


def test_tmdb_failure_maps_to_502(
    client_factory: Callable[..., TestClient],
    alice: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(key: str, q: str) -> list[Movie]:
        raise TMDBError("TMDB returned 500")

    monkeypatch.setattr("app.routers.tmdb.search_movies", boom)
    resp = client_factory(alice).get("/api/tmdb/search", params={"q": "x"})
    assert resp.status_code == 502


def test_tmdb_not_configured_maps_to_503(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    # No TMDB_API_KEY in the test settings -> a clear 503, not a crash.
    resp = client_factory(alice).get("/api/tmdb/search", params={"q": "x"})
    assert resp.status_code == 503
