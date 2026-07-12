"""TMDB API client.

Kept in its own module so routes stay thin and tests can monkeypatch these two
functions without any network access. The API key never leaves the backend —
the browser only ever talks to our /api/tmdb/* proxy.

Uses TMDB v3 auth (the "API Key" from themoviedb.org -> Settings -> API).
Poster images are public and built client-side from `poster_path`, so they need
no key: https://image.tmdb.org/t/p/w200{poster_path}
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT_SECONDS = 10.0

# Some networks intermittently reset connections to api.themoviedb.org
# (WinError 10054 / "connection reset"). These surface as httpx.TransportError
# subclasses -- ReadError, ConnectError, etc. Every call here is a GET (a safe,
# idempotent read), so retrying the whole request is correct.
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 0.3


class TMDBError(RuntimeError):
    """TMDB was unreachable or returned an error. Routes map this to a 502."""


class TMDBNotConfigured(RuntimeError):
    """No TMDB_API_KEY is set. Routes map this to a 503."""


@dataclass
class Movie:
    tmdb_id: int
    title: str
    release_year: int | None
    poster_path: str | None
    overview: str | None


def _release_year(release_date: str | None) -> int | None:
    # TMDB gives "1999-03-31", or "" / null when unknown.
    if not release_date:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


def _to_movie(raw: dict) -> Movie:
    return Movie(
        tmdb_id=raw["id"],
        title=raw.get("title") or raw.get("original_title") or "Untitled",
        release_year=_release_year(raw.get("release_date")),
        poster_path=raw.get("poster_path"),
        overview=raw.get("overview") or None,
    )


def _fetch(url: str, params: dict) -> httpx.Response:
    """One HTTP GET. Split out so the retry loop (and tests) can drive it."""
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        return client.get(url, params=params)


def _get(api_key: str, path: str, params: dict) -> dict:
    if not api_key:
        raise TMDBNotConfigured("TMDB_API_KEY is not set")

    url = f"{BASE_URL}{path}"
    query = {"api_key": api_key, **params}
    last_error = ""

    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = _fetch(url, query)
        except httpx.TransportError as exc:
            # Connection reset / timeout / DNS blip — retry.
            last_error = f"TMDB request failed: {exc}"
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code < 500:
                # 401 bad key, 404 unknown movie — retrying won't help.
                raise TMDBError(f"TMDB returned {resp.status_code}")
            last_error = f"TMDB returned {resp.status_code}"

        if attempt < MAX_ATTEMPTS - 1:
            time.sleep(BACKOFF_SECONDS * (2**attempt))

    raise TMDBError(f"{last_error} (after {MAX_ATTEMPTS} attempts)")


def search_movies(api_key: str, query: str) -> list[Movie]:
    """Search movies by title. Returns a trimmed list (no raw TMDB payload)."""
    data = _get(
        api_key,
        "/search/movie",
        {"query": query, "include_adult": "false", "language": "en-US", "page": 1},
    )
    return [_to_movie(raw) for raw in data.get("results", [])]


def get_movie(api_key: str, tmdb_id: int) -> Movie:
    """Fetch one movie's metadata — used to snapshot it when adding to a list."""
    return _to_movie(_get(api_key, f"/movie/{tmdb_id}", {"language": "en-US"}))
