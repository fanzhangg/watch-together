"""Retry behavior of the TMDB client.

Real networks reset connections to api.themoviedb.org intermittently
(WinError 10054). Every TMDB call is a GET, so retrying the whole request is
safe — but we must not retry things retrying can't fix (401/404), and we must
give up eventually rather than hang.
"""

from __future__ import annotations

import httpx
import pytest

from app import tmdb
from app.tmdb import (
    TMDBError,
    TMDBNotConfigured,
    TMDBNotFound,
    get_movie,
    search_movies,
)

MATRIX_PAYLOAD = {
    "id": 603,
    "title": "The Matrix",
    "release_date": "1999-03-30",
    "poster_path": "/m.jpg",
    "overview": "A hacker learns the truth.",
}


def _response(status: int, json_body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=json_body if json_body is not None else {},
        request=httpx.Request("GET", "https://api.themoviedb.org/3/movie/603"),
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Don't actually wait during backoff."""
    monkeypatch.setattr("app.tmdb.time.sleep", lambda _s: None)


def test_transient_reset_is_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def flaky(url: str, params: dict) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:  # first two attempts get reset
            raise httpx.ReadError("connection forcibly closed (WinError 10054)")
        return _response(200, MATRIX_PAYLOAD)

    monkeypatch.setattr(tmdb, "_fetch", flaky)

    movie = get_movie("key", 603)
    assert movie.title == "The Matrix"
    assert movie.release_year == 1999
    assert calls["n"] == 3  # it retried rather than failing


def test_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def always_reset(url: str, params: dict) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadError("connection forcibly closed")

    monkeypatch.setattr(tmdb, "_fetch", always_reset)

    with pytest.raises(TMDBError):
        get_movie("key", 603)
    assert calls["n"] == tmdb.MAX_ATTEMPTS  # bounded, doesn't hang


def test_client_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401 (bad key) won't fix itself — fail fast instead of hammering TMDB."""
    calls = {"n": 0}

    def unauthorized(url: str, params: dict) -> httpx.Response:
        calls["n"] += 1
        return _response(401)

    monkeypatch.setattr(tmdb, "_fetch", unauthorized)

    with pytest.raises(TMDBError):
        search_movies("bad-key", "matrix")
    assert calls["n"] == 1


def test_not_found_raises_not_found_and_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown movie id is a caller mistake: distinct exception, no retries."""
    calls = {"n": 0}

    def missing(url: str, params: dict) -> httpx.Response:
        calls["n"] += 1
        return _response(404)

    monkeypatch.setattr(tmdb, "_fetch", missing)

    with pytest.raises(TMDBNotFound):
        get_movie("key", 99999999)
    assert calls["n"] == 1


def test_server_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky_500(url: str, params: dict) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return _response(503)
        return _response(200, {"results": [MATRIX_PAYLOAD]})

    monkeypatch.setattr(tmdb, "_fetch", flaky_500)

    movies = search_movies("key", "matrix")
    assert [m.tmdb_id for m in movies] == [603]
    assert calls["n"] == 2


def test_missing_key_raises_before_any_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def should_not_run(url: str, params: dict) -> httpx.Response:
        raise AssertionError("must not call TMDB without a key")

    monkeypatch.setattr(tmdb, "_fetch", should_not_run)

    with pytest.raises(TMDBNotConfigured):
        search_movies("", "matrix")
