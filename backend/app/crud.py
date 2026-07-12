"""Database helpers shared across routers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ROLE_MEMBER,
    ROLE_OWNER,
    STATUS_WATCHED,
    List,
    ListItem,
    ListMember,
    User,
)
from app.tmdb import Movie

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


# --- Lists ---------------------------------------------------------------
def create_list(db: Session, *, owner: User, name: str) -> List:
    """Create a list and make the owner its first (owner-role) member."""
    lst = List(name=name, owner_id=owner.id)
    db.add(lst)
    db.flush()  # assign lst.id before inserting the membership row
    db.add(ListMember(list_id=lst.id, user_id=owner.id, role=ROLE_OWNER))
    db.commit()
    db.refresh(lst)
    return lst


def lists_for_user(db: Session, user_id: uuid.UUID) -> list[tuple[List, str]]:
    """Return (list, caller's role) for every list the user is a member of."""
    rows = db.execute(
        select(List, ListMember.role)
        .join(ListMember, ListMember.list_id == List.id)
        .where(ListMember.user_id == user_id)
        .order_by(List.created_at)
    ).all()
    return [(lst, role) for lst, role in rows]


def get_membership(
    db: Session, list_id: uuid.UUID, user_id: uuid.UUID
) -> ListMember | None:
    return db.execute(
        select(ListMember).where(
            ListMember.list_id == list_id, ListMember.user_id == user_id
        )
    ).scalar_one_or_none()


def get_members(db: Session, list_id: uuid.UUID) -> list[tuple[User, str]]:
    rows = db.execute(
        select(User, ListMember.role)
        .join(ListMember, ListMember.user_id == User.id)
        .where(ListMember.list_id == list_id)
        .order_by(ListMember.joined_at)
    ).all()
    return [(user, role) for user, role in rows]


def rename_list(db: Session, lst: List, name: str) -> List:
    lst.name = name
    db.commit()
    db.refresh(lst)
    return lst


def delete_list(db: Session, lst: List) -> None:
    db.delete(lst)
    db.commit()


# --- List items (movies) -------------------------------------------------
def _mark_status(item: ListItem, status: str) -> None:
    """Status is the source of truth; watched_at is derived from it."""
    item.status = status
    item.watched_at = datetime.now(timezone.utc) if status == STATUS_WATCHED else None


def get_items(db: Session, list_id: uuid.UUID) -> list[ListItem]:
    return list(
        db.execute(
            select(ListItem)
            .where(ListItem.list_id == list_id)
            .order_by(ListItem.created_at)
        ).scalars()
    )


def get_item(db: Session, list_id: uuid.UUID, item_id: uuid.UUID) -> ListItem | None:
    return db.execute(
        select(ListItem).where(ListItem.id == item_id, ListItem.list_id == list_id)
    ).scalar_one_or_none()


def get_item_by_tmdb(db: Session, list_id: uuid.UUID, tmdb_id: int) -> ListItem | None:
    return db.execute(
        select(ListItem).where(
            ListItem.list_id == list_id, ListItem.tmdb_id == tmdb_id
        )
    ).scalar_one_or_none()


def add_item(
    db: Session,
    *,
    list_id: uuid.UUID,
    added_by: User,
    movie: Movie,
    status: str,
) -> tuple[ListItem, bool]:
    """Add a movie to a list. Returns (item, created).

    Adding a film already in the list is idempotent: the existing row is
    returned rather than raising on UNIQUE(list_id, tmdb_id). The IntegrityError
    path covers two members adding the same film concurrently.
    """
    existing = db.execute(
        select(ListItem).where(
            ListItem.list_id == list_id, ListItem.tmdb_id == movie.tmdb_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    item = ListItem(
        list_id=list_id,
        tmdb_id=movie.tmdb_id,
        title=movie.title,
        release_year=movie.release_year,
        poster_path=movie.poster_path,
        overview=movie.overview,
        added_by=added_by.id,
    )
    _mark_status(item, status)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent add — fall back to the winner's row.
        db.rollback()
        existing = db.execute(
            select(ListItem).where(
                ListItem.list_id == list_id, ListItem.tmdb_id == movie.tmdb_id
            )
        ).scalar_one()
        return existing, False

    db.refresh(item)
    return item, True


def set_item_status(db: Session, item: ListItem, status: str) -> ListItem:
    _mark_status(item, status)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: ListItem) -> None:
    db.delete(item)
    db.commit()
