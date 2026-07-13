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
from dataclasses import dataclass, field

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


class TMDBNotFound(RuntimeError):
    """TMDB has no such movie. A caller mistake, so routes map this to a 404
    rather than a 502 — it isn't a gateway failure."""


@dataclass
class Movie:
    tmdb_id: int
    title: str
    release_year: int | None
    poster_path: str | None
    overview: str | None


@dataclass
class MovieDetail(Movie):
    """Everything the detail page shows. Fetched live and never stored — the
    board renders from the DB snapshot, so a TMDB outage costs one page, not the
    app."""

    backdrop_path: str | None = None
    tagline: str | None = None
    runtime: int | None = None
    genres: list[str] = field(default_factory=list)
    vote_average: float | None = None
    director: str | None = None
    cast: list[str] = field(default_factory=list)


# The detail page shows a handful of names, not a full unit list.
TOP_CAST = 8


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
            if resp.status_code == 404:
                # The caller asked for a movie that doesn't exist — not our fault.
                raise TMDBNotFound(f"No TMDB movie for {path}")
            if resp.status_code < 500:
                # e.g. 401 bad key — retrying won't help.
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


def get_movie_detail(api_key: str, tmdb_id: int) -> MovieDetail:
    """Fetch the full metadata the detail page renders.

    `append_to_response=credits` folds the cast/crew into the same request, so
    the page costs one TMDB call rather than two.
    """
    raw = _get(
        api_key,
        f"/movie/{tmdb_id}",
        {"language": "en-US", "append_to_response": "credits"},
    )
    credits = raw.get("credits") or {}
    director = next(
        (
            person["name"]
            for person in credits.get("crew", [])
            if person.get("job") == "Director"
        ),
        None,
    )
    base = _to_movie(raw)

    return MovieDetail(
        tmdb_id=base.tmdb_id,
        title=base.title,
        release_year=base.release_year,
        poster_path=base.poster_path,
        overview=base.overview,
        backdrop_path=raw.get("backdrop_path"),
        tagline=raw.get("tagline") or None,
        # TMDB sends 0 for "unknown runtime" — that's a null, not a 0-minute film.
        runtime=raw.get("runtime") or None,
        genres=[g["name"] for g in raw.get("genres", []) if g.get("name")],
        vote_average=raw.get("vote_average") or None,
        director=director,
        cast=[
            person["name"]
            for person in credits.get("cast", [])[:TOP_CAST]
            if person.get("name")
        ],
    )
