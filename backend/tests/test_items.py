"""M3/M7 tests: TMDB proxy + movie item lifecycle + the watch date.

TMDB is mocked throughout — no network and no API key needed. Covers the
stateful bit that actually has logic (status <-> watched_on) and the duplicate
add being idempotent rather than a 500.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ListItem, User
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
    assert body["watched_on"] is None
    assert body["added_by"] == str(alice.id)

    listed = ca.get(f"/api/lists/{lid}/items").json()
    assert [i["tmdb_id"] for i in listed] == [603]


def test_get_single_item(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    """The detail page deep-links, so it must load without the list in cache."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    got = ca.get(f"/api/lists/{lid}/items/{iid}")
    assert got.status_code == 200
    assert got.json()["title"] == "The Matrix"

    assert ca.get(f"/api/lists/{lid}/items/{uuid.uuid4()}").status_code == 404


# --- M7: the watch date ---------------------------------------------------
def test_status_toggle_sets_and_clears_watched_on(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    """Marking watched without a date stamps the server's today; unwatching
    clears it. status and watched_on are never out of step."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    watched = ca.patch(f"/api/lists/{lid}/items/{iid}", json={"status": "watched"})
    assert watched.status_code == 200
    assert watched.json()["status"] == "watched"
    assert watched.json()["watched_on"] == date.today().isoformat()

    unwatched = ca.patch(
        f"/api/lists/{lid}/items/{iid}", json={"status": "want_to_watch"}
    )
    assert unwatched.json()["status"] == "want_to_watch"
    assert unwatched.json()["watched_on"] is None


def test_mark_watched_on_a_given_day(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    """What the UI actually sends: the user's own local today (or any past day)."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]

    resp = ca.patch(
        f"/api/lists/{lid}/items/{iid}",
        json={"status": "watched", "watched_on": "2026-07-04"},
    )
    assert resp.status_code == 200
    assert resp.json()["watched_on"] == "2026-07-04"

    # And the date can be moved afterwards, without re-sending the status.
    moved = ca.patch(f"/api/lists/{lid}/items/{iid}", json={"watched_on": "2026-06-01"})
    assert moved.status_code == 200
    assert moved.json()["watched_on"] == "2026-06-01"
    assert moved.json()["status"] == "watched"


def test_unwatching_forgets_the_date(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    """Re-watching does not silently resurrect the old date — it's today again."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]
    url = f"/api/lists/{lid}/items/{iid}"

    ca.patch(url, json={"status": "watched", "watched_on": "2026-01-01"})
    ca.patch(url, json={"status": "want_to_watch"})
    again = ca.patch(url, json={"status": "watched"})

    assert again.json()["watched_on"] == date.today().isoformat()


def test_tomorrow_is_allowed_but_next_week_is_not(
    client_factory: Callable[..., TestClient], alice: User, mock_tmdb: None
) -> None:
    """The client sends its LOCAL today, which can legitimately be a day ahead of
    the server's UTC today. Tolerate exactly that — you can't have watched a film
    next week."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]
    url = f"/api/lists/{lid}/items/{iid}"
    today = date.today()

    ahead = ca.patch(
        url,
        json={
            "status": "watched",
            "watched_on": (today + timedelta(days=1)).isoformat(),
        },
    )
    assert ahead.status_code == 200

    far = ca.patch(
        url,
        json={
            "status": "watched",
            "watched_on": (today + timedelta(days=7)).isoformat(),
        },
    )
    assert far.status_code == 422


@pytest.mark.parametrize(
    ("body", "start_watched"),
    [
        # A date on a movie that isn't watched — would break the CHECK.
        ({"watched_on": "2026-07-04"}, False),
        ({"status": "want_to_watch", "watched_on": "2026-07-04"}, True),
        # Blanking the date of a watched movie — unwatch it instead.
        ({"watched_on": None}, True),
        # Nothing to do.
        ({}, False),
    ],
)
def test_incoherent_updates_are_rejected(
    client_factory: Callable[..., TestClient],
    alice: User,
    mock_tmdb: None,
    body: dict,
    start_watched: bool,
) -> None:
    """Contradictions are 422s, not silent repairs — they can only be client bugs."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]
    url = f"/api/lists/{lid}/items/{iid}"
    if start_watched:
        ca.patch(url, json={"status": "watched", "watched_on": "2026-07-04"})

    assert ca.patch(url, json=body).status_code == 422


def test_watched_is_always_dated(
    client_factory: Callable[..., TestClient],
    alice: User,
    mock_tmdb: None,
    db_session: Session,
) -> None:
    """The DB itself refuses a watched-but-undated row, so no code path anywhere
    has to handle one."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    iid = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": 603}).json()["id"]
    ca.patch(f"/api/lists/{lid}/items/{iid}", json={"status": "watched"})

    item = db_session.get(ListItem, uuid.UUID(iid))
    assert item is not None
    item.watched_on = None
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


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
