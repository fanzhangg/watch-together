"""Movies inside a list. Every route is membership-gated (any member can edit)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import ListContext, get_current_user, require_list_member
from app.models import User
from app.schemas import ItemCreate, ItemOut, ItemUpdate
from app.tmdb import TMDBError, TMDBNotConfigured, TMDBNotFound, get_movie

router = APIRouter(prefix="/api/lists/{list_id}/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
def get_items(
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    return [ItemOut.model_validate(i) for i in crud.get_items(db, ctx.list.id)]


@router.post(
    "",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a movie to the list",
    responses={
        201: {"description": "Movie added to the list"},
        200: {
            "model": ItemOut,
            "description": "Movie was already in the list — the existing item is "
            "returned unchanged (idempotent; no TMDB call is made)",
        },
        403: {"description": "Not a member of this list"},
        404: {"description": "TMDB has no movie with that id"},
        502: {"description": "TMDB is unreachable"},
        503: {"description": "TMDB is not configured (TMDB_API_KEY unset)"},
    },
)
def add_item(
    payload: ItemCreate,
    response: Response,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ItemOut:
    """Add a movie by TMDB id; the backend snapshots its metadata.

    Idempotent: re-adding a film already in the list returns the existing item
    with 200 instead of failing on the UNIQUE constraint. The existence check
    happens BEFORE the TMDB call, so a duplicate add costs no network request
    and still succeeds even when TMDB is unreachable.
    """
    existing = crud.get_item_by_tmdb(db, ctx.list.id, payload.tmdb_id)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return ItemOut.model_validate(existing)

    try:
        movie = get_movie(settings.tmdb_api_key, payload.tmdb_id)
    except TMDBNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TMDB is not configured (set TMDB_API_KEY)",
        )
    except TMDBNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TMDB has no movie with id {payload.tmdb_id}",
        )
    except TMDBError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    item, created = crud.add_item(
        db,
        list_id=ctx.list.id,
        added_by=user,
        movie=movie,
        status=payload.status,
    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return ItemOut.model_validate(item)


@router.get(
    "/{item_id}",
    response_model=ItemOut,
    summary="One movie in the list",
    responses={
        200: {"description": "The item"},
        403: {"description": "Not a member of this list"},
        404: {"description": "No such item in this list"},
    },
)
def get_item(
    item_id: uuid.UUID,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> ItemOut:
    """Lets the detail page load on its own — a deep link or a hard refresh has
    no items list in the cache to read from."""
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")
    return ItemOut.model_validate(item)


@router.patch(
    "/{item_id}",
    response_model=ItemOut,
    summary="Change a movie's watched status and/or watch date",
    responses={
        200: {"description": "Updated; status and watched_on stay in lockstep"},
        403: {"description": "Not a member of this list"},
        404: {"description": "No such item in this list"},
        422: {
            "description": "Incoherent update — a date on an unwatched movie, a "
            "null date on a watched one, or a date in the future"
        },
    },
)
def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> ItemOut:
    """Marking watched without a date stamps the server's today; the UI instead
    sends the user's LOCAL today, so we never have to guess their timezone."""
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")

    try:
        updated = crud.update_item(
            db,
            item,
            status=payload.status,
            watched_on=payload.watched_on,
            sets_watched_on=payload.sets_watched_on,
        )
    except crud.ItemUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return ItemOut.model_validate(updated)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a movie from the list",
    responses={
        204: {"description": "Movie removed"},
        403: {"description": "Not a member of this list"},
        404: {"description": "No such item in this list"},
    },
)
def delete_item(
    item_id: uuid.UUID,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> Response:
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")
    crud.delete_item(db, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
