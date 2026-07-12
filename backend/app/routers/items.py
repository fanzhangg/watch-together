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
from app.tmdb import TMDBError, TMDBNotConfigured, get_movie

router = APIRouter(prefix="/api/lists/{list_id}/items", tags=["items"])


@router.get("", response_model=list[ItemOut])
def get_items(
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> list[ItemOut]:
    return [ItemOut.model_validate(i) for i in crud.get_items(db, ctx.list.id)]


@router.post("", response_model=ItemOut)
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
    with 200 instead of failing on the UNIQUE constraint.
    """
    try:
        movie = get_movie(settings.tmdb_api_key, payload.tmdb_id)
    except TMDBNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TMDB is not configured (set TMDB_API_KEY)",
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


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> ItemOut:
    item = crud.get_item(db, ctx.list.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such item")
    return ItemOut.model_validate(crud.set_item_status(db, item, payload.status))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
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
