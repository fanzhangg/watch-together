"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
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
