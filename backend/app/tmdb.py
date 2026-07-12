"""TMDB API client.

Kept in its own module so routes stay thin and tests can monkeypatch these two
functions without any network access. The API key never leaves the backend —
the browser only ever talks to our /api/tmdb/* proxy.

Uses TMDB v3 auth (the "API Key" from themoviedb.org -> Settings -> API).
Poster images are public and built client-side from `poster_path`, so they need
no key: https://image.tmdb.org/t/p/w200{poster_path}
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT_SECONDS = 10.0
# Connections to TMDB are occasionally reset mid-handshake on some networks.
# httpx retries only connection-level failures here (never a completed request),
# so this is safe for the non-idempotent-looking GETs too.
CONNECT_RETRIES = 3


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


def _get(api_key: str, path: str, params: dict) -> dict:
    if not api_key:
        raise TMDBNotConfigured("TMDB_API_KEY is not set")
    transport = httpx.HTTPTransport(retries=CONNECT_RETRIES)
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS) as client:
            resp = client.get(
                f"{BASE_URL}{path}", params={"api_key": api_key, **params}
            )
    except httpx.HTTPError as exc:  # network/timeout, after retries
        raise TMDBError(f"TMDB request failed: {exc}") from exc
    if resp.status_code != 200:
        raise TMDBError(f"TMDB returned {resp.status_code}")
    return resp.json()


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
