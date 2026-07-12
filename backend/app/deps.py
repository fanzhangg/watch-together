"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import crud
from app.config import Settings, get_settings
from app.db import get_db
from app.models import ROLE_OWNER, List, ListMember, User
from app.security import read_session

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the logged-in user from the session cookie, or raise 401."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _UNAUTHENTICATED

    user_id = read_session(settings, token)
    if not user_id:
        raise _UNAUTHENTICATED

    try:
        pk = uuid.UUID(user_id)
    except ValueError:
        raise _UNAUTHENTICATED

    user = db.get(User, pk)
    if user is None:
        raise _UNAUTHENTICATED
    return user


@dataclass
class ListContext:
    """A list the caller is allowed to access, plus their membership row."""

    list: List
    membership: ListMember


def require_list_member(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ListContext:
    """Gate every /lists/{list_id}/* route on membership. 403 if not a member.

    Returning 403 (not 404) for both non-member and non-existent lists avoids
    leaking which list ids exist.
    """
    membership = crud.get_membership(db, list_id, user.id)
    lst = db.get(List, list_id) if membership is not None else None
    if membership is None or lst is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this list"
        )
    return ListContext(list=lst, membership=membership)


def require_list_owner(ctx: ListContext = Depends(require_list_member)) -> ListContext:
    """Stronger gate for owner-only actions (rename, delete)."""
    if ctx.membership.role != ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Owner action"
        )
    return ctx
