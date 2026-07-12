"""Database helpers shared across routers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ROLE_MEMBER, ROLE_OWNER, List, ListMember, User

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
