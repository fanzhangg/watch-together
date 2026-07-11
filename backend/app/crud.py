"""Database helpers shared across routers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

# Stable identity for the local dev-login user (DEV_LOGIN=1 only).
DEV_USER_SUB = "dev-login-user"
DEV_USER_EMAIL = "dev@local"


def upsert_user_by_google(
    db: Session,
    *,
    google_sub: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
) -> User:
    """Find a user by google_sub (or email), creating/updating as needed."""
    user = db.execute(
        select(User).where(User.google_sub == google_sub)
    ).scalar_one_or_none()
    if user is None:
        # Fall back to matching an existing account by email (e.g. a dev user
        # that later signs in with Google using the same address).
        user = db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        db.add(user)
    else:
        user.google_sub = google_sub
        user.email = email
        user.display_name = display_name
        user.avatar_url = avatar_url

    db.commit()
    db.refresh(user)
    return user


def get_or_create_dev_user(db: Session) -> User:
    """Return the local dev user, creating it on first use."""
    user = db.execute(
        select(User).where(User.google_sub == DEV_USER_SUB)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            google_sub=DEV_USER_SUB,
            email=DEV_USER_EMAIL,
            display_name="Dev User",
            avatar_url=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
