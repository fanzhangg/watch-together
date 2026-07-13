"""TMDB search proxy.

The browser never sees the API key — it calls this, we call TMDB. Auth-gated so
the proxy can't be used by anonymous callers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings, get_settings
from app.deps import get_current_user
from app.models import User
from app.schemas import MovieDetail, MovieSearchResult
from app.tmdb import (
    TMDBError,
    TMDBNotConfigured,
    TMDBNotFound,
    get_movie_detail,
    search_movies,
)

router = APIRouter(prefix="/api/tmdb", tags=["tmdb"])


@router.get(
    "/search",
    response_model=list[MovieSearchResult],
    summary="Search TMDB for movies by title",
    responses={
        200: {"description": "Matching movies (may be an empty list)"},
        401: {"description": "Not authenticated"},
        502: {"description": "TMDB is unreachable"},
        503: {"description": "TMDB is not configured (TMDB_API_KEY unset)"},
    },
)
def search(
    q: str = Query(min_length=1, description="Movie title to search for"),
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MovieSearchResult]:
    try:
        movies = search_movies(settings.tmdb_api_key, q)
    except TMDBNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TMDB is not configured (set TMDB_API_KEY)",
        )
    except TMDBError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return [MovieSearchResult.model_validate(m) for m in movies]


@router.get(
    "/movie/{tmdb_id}",
    response_model=MovieDetail,
    summary="Full TMDB metadata for the movie detail page",
    responses={
        200: {"description": "Runtime, genres, tagline, rating, director, top cast"},
        401: {"description": "Not authenticated"},
        404: {"description": "TMDB has no movie with that id"},
        502: {"description": "TMDB is unreachable"},
        503: {"description": "TMDB is not configured (TMDB_API_KEY unset)"},
    },
)
def movie_detail(
    tmdb_id: int,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MovieDetail:
    """Live, not snapshotted. The detail page degrades to the DB snapshot when
    this fails, so a TMDB outage never blocks reading or editing the list."""
    try:
        movie = get_movie_detail(settings.tmdb_api_key, tmdb_id)
    except TMDBNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TMDB is not configured (set TMDB_API_KEY)",
        )
    except TMDBNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TMDB has no movie with id {tmdb_id}",
        )
    except TMDBError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return MovieDetail.model_validate(movie)
