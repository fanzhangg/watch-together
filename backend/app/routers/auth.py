"""Authentication routes.

- POST /api/auth/google     verify a Google ID token, upsert user, set session
- POST /api/auth/dev-login  local-only bypass (DEV_LOGIN=1), set session
- GET  /api/auth/me         current user (401 if not logged in)
- POST /api/auth/logout     clear the session cookie
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.auth_google import verify_google_token
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import GoogleLoginIn, UserOut
from app.security import issue_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, settings: Settings, user: User) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=issue_session(settings, str(user.id)),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/google", response_model=UserOut)
def login_google(
    payload: GoogleLoginIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    try:
        identity = verify_google_token(payload.credential, settings.google_client_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
        )
    user = crud.upsert_user_by_google(
        db,
        google_sub=identity.sub,
        email=identity.email,
        display_name=identity.name,
        avatar_url=identity.picture,
    )
    _set_session_cookie(response, settings, user)
    return user


@router.post("/dev-login", response_model=UserOut)
def dev_login(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not settings.dev_login:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    user = crud.get_or_create_dev_user(db)
    _set_session_cookie(response, settings, user)
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/logout")
def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}
