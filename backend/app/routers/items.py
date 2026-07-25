"""Movies inside a list. Every route is membership-gated (any member can edit)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import ListContext, get_current_user, require_list_member
from app.models import ItemRating, ListItem, User
from app.schemas import (
    ItemCreate,
    ItemOut,
    ItemUpdate,
    MyRatingOut,
    RatingIn,
    RatingOut,
)
from app.tmdb import TMDBError, TMDBNotConfigured, TMDBNotFound, get_movie

router = APIRouter(prefix="/api/lists/{list_id}/items", tags=["items"])


def _with_ratings(
    item: ListItem, by_item: dict[uuid.UUID, list[ItemRating]]
) -> ItemOut:
    """Attach verdicts to an item.

    Stitched on from one crud.ratings_for_list call rather than loaded per item
    — a lazy relationship would issue a query per card on the board.
    """
    out = ItemOut.model_validate(item)
    out.ratings = [RatingOut.model_validate(r) for r in by_item.get(item.id, ())]
    return out


def _one_with_ratings(
    db: Session, list_id: uuid.UUID, item: ListItem
) -> ItemOut:
    """Same, for a single item — scoped so it doesn't read the whole board."""
    return _with_ratings(item, crud.ratings_for_list(db, list_id, [item.id]))


@router.get("", response_model=list[ItemOut])
def get_items(
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    items = crud.get_items(db, ctx.list.id)
    # One query for the whole board's verdicts, not one per card.
    by_film = crud.ratings_for_list(db, ctx.list.id)
    return [_with_ratings(i, by_film) for i in items]


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
        return _one_with_ratings(db, ctx.list.id, existing)

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
    # A new item has no verdicts; a re-added one is a new row, so it has none
    # either — removing a movie takes the opinions about it with it.
    return _one_with_ratings(db, ctx.list.id, item)


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
    return _one_with_ratings(db, ctx.list.id, item)


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
    # Verdicts are untouched by a status change — the two facts are independent
    # (docs/design.md §12). Re-read them so the client's cache stays whole.
    return _one_with_ratings(db, ctx.list.id, updated)


@router.put(
    "/{item_id}/rating",
    response_model=MyRatingOut,
    summary="Set my verdict on this movie",
    responses={
        200: {"description": "Verdict recorded (or flipped)"},
        403: {"description": "Not a member of this list"},
        404: {"description": "No such item in this list"},
        422: {"description": "value must be 1 or -1"},
    },
)
def set_rating(
    item_id: uuid.UUID,
    payload: RatingIn,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MyRatingOut:
    """Record my thumbs up/down on this movie, in this list.

    The verdict is scoped to the list item, so the same film sitting in another
    list keeps its own separate verdicts — a thumb is aimed at the people in
    *this* list, and it stays there.

    **No watched check.** Rating and watch status are independent facts; a thumb
    on an unwatched film reads as "I'm keen", one on a watched film as "I liked
    it", and the item's status is what tells them apart.
    """
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")

    rating = crud.set_rating(db, user=user, item=item, value=payload.value)
    return MyRatingOut(item_id=rating.list_item_id, value=rating.value)


@router.delete(
    "/{item_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Take back my verdict on this movie",
    responses={
        204: {
            "description": "No verdict of mine remains — including when there "
            "wasn't one to begin with (idempotent)"
        },
        403: {"description": "Not a member of this list"},
        404: {"description": "No such item in this list"},
    },
)
def clear_rating(
    item_id: uuid.UUID,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Clears only *my* verdict — a member can never touch anyone else's."""
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")

    crud.clear_rating(db, user=user, item=item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
