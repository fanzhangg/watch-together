"""Database helpers shared across routers."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ROLE_MEMBER,
    ROLE_OWNER,
    STATUS_WANT,
    STATUS_WATCHED,
    Invite,
    List,
    ItemRating,
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


def _dev_slug(name: str) -> str:
    """"Fang Zhang" -> "fang-zhang". Stable, so the same name is the same person."""
    cleaned = [c.lower() if c.isalnum() else "-" for c in name.strip()]
    return "-".join(filter(None, "".join(cleaned).split("-")))


def get_or_create_dev_user(db: Session, name: str | None = None) -> User:
    """Return a local dev user, creating it on first use.

    With no name, this is the single default dev user. **With a name it's a
    separate, stable identity** (`dev-login-user-fang` / `fang@local`) — which is
    how the two-person experience gets driven locally: two browser profiles, two
    different names, one list shared between them by invite link. Without it
    every profile signs in as the same person and nothing multi-user can be seen.

    The name is an identity, not a password. This route only exists when
    DEV_LOGIN is on, which is never true in production.
    """
    slug = _dev_slug(name) if name else ""
    if not slug:
        sub, email, display = DEV_USER_SUB, DEV_USER_EMAIL, "Dev User"
    else:
        sub, email, display = (
            f"{DEV_USER_SUB}-{slug}",
            f"{slug}@local",
            (name or "").strip(),
        )

    user = db.execute(
        select(User).where(User.google_sub == sub)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            google_sub=sub,
            email=email,
            display_name=display,
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
        # user_id breaks ties: SQLite's CURRENT_TIMESTAMP only has second
        # granularity, so two people who joined in the same second would
        # otherwise come back in whatever order the database chose that time —
        # and the member avatars would shuffle between renders.
        .order_by(ListMember.joined_at, ListMember.user_id)
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
class ItemUpdateError(ValueError):
    """An update that would leave the row incoherent. Routes map this to a 422."""


def _server_today() -> date:
    return datetime.now(timezone.utc).date()


def _mark_status(item: ListItem, status: str, watched_on: date | None = None) -> None:
    """Keep status and watched_on in lockstep (the DB CHECK requires it)."""
    item.status = status
    if status == STATUS_WATCHED:
        item.watched_on = watched_on or _server_today()
    else:
        item.watched_on = None


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


# --- Invites -------------------------------------------------------------
# 16 random bytes -> ~22 url-safe chars. The code IS the secret that grants
# access, so it must come from a CSPRNG (secrets), never random/uuid1.
INVITE_CODE_BYTES = 16


def create_invite(
    db: Session,
    *,
    list_id: uuid.UUID,
    created_by: User,
    expires_in_days: int | None = None,
) -> Invite:
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        if expires_in_days is not None
        else None
    )
    invite = Invite(
        list_id=list_id,
        code=secrets.token_urlsafe(INVITE_CODE_BYTES),
        created_by=created_by.id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def get_invite_by_code(db: Session, code: str) -> Invite | None:
    return db.execute(
        select(Invite).where(Invite.code == code)
    ).scalar_one_or_none()


def invite_is_expired(invite: Invite) -> bool:
    if invite.expires_at is None:
        return False
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        # SQLite round-trips naive datetimes; treat them as UTC.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def accept_invite(db: Session, invite: Invite, user: User) -> ListMember:
    """Join the invite's list. Idempotent, and never changes an existing role —
    re-accepting must not demote the owner to a plain member."""
    existing = get_membership(db, invite.list_id, user.id)
    if existing is not None:
        return existing

    membership = ListMember(
        list_id=invite.list_id, user_id=user.id, role=ROLE_MEMBER
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        # Raced with another accept of the same invite.
        db.rollback()
        existing = get_membership(db, invite.list_id, user.id)
        if existing is None:
            raise
        return existing
    db.refresh(membership)
    return membership


def update_item(
    db: Session,
    item: ListItem,
    *,
    status: str | None,
    watched_on: date | None,
    sets_watched_on: bool,
) -> ListItem:
    """Apply a PATCH to an item. See the semantics table in docs/design.md §5.

    `sets_watched_on` says whether the caller sent the field at all, which is the
    only way to tell "leave the date alone" from "blank the date".
    """
    target_status = status or item.status

    if target_status == STATUS_WANT:
        if sets_watched_on and watched_on is not None:
            # Only reachable when status was omitted; the schema catches the
            # explicit want_to_watch + date combination.
            raise ItemUpdateError("an unwatched movie cannot have a watch date")
        _mark_status(item, STATUS_WANT)
    elif sets_watched_on:
        if watched_on is None:
            raise ItemUpdateError(
                "a watched movie must have a watch date — unwatch it instead"
            )
        _mark_status(item, STATUS_WATCHED, watched_on)
    else:
        # No date given: keep the one it has, or stamp today if it's newly watched.
        _mark_status(item, STATUS_WATCHED, item.watched_on)

    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: ListItem) -> None:
    db.delete(item)
    db.commit()


# --- Ratings (M8) --------------------------------------------------------
def get_rating(
    db: Session, list_item_id: uuid.UUID, user_id: uuid.UUID
) -> ItemRating | None:
    return db.execute(
        select(ItemRating).where(
            ItemRating.list_item_id == list_item_id,
            ItemRating.user_id == user_id,
        )
    ).scalar_one_or_none()


def ratings_for_list(
    db: Session,
    list_id: uuid.UUID,
    item_ids: Sequence[uuid.UUID] | None = None,
) -> dict[uuid.UUID, list[ItemRating]]:
    """Verdicts on this list's movies, keyed by list item.

    A verdict is scoped to the list item, so **the scoping is the foreign key,
    not this query** — an opinion recorded in another list is not reachable from
    here even if every filter below were wrong. The `list_members` join is here
    for two lesser reasons: it orders verdicts by `joined_at`, so they appear in
    the same order every render instead of whatever the database feels like, and
    it drops anyone no longer in the list.

    One query for a whole board, never one per item. `item_ids` narrows it for
    the single-item route.
    """
    stmt = (
        select(ItemRating)
        .join(ListItem, ListItem.id == ItemRating.list_item_id)
        .join(
            ListMember,
            (ListMember.user_id == ItemRating.user_id)
            & (ListMember.list_id == ListItem.list_id),
        )
        .where(ListItem.list_id == list_id)
        # Same tiebreak as get_members, so both come out in the same order.
        .order_by(ListMember.joined_at, ItemRating.user_id)
    )

    if item_ids is not None:
        ids = list(item_ids)
        if not ids:
            return {}
        stmt = stmt.where(ItemRating.list_item_id.in_(ids))

    by_item: dict[uuid.UUID, list[ItemRating]] = {}
    for rating in db.execute(stmt).scalars():
        by_item.setdefault(rating.list_item_id, []).append(rating)
    return by_item


def set_rating(db: Session, *, user: User, item: ListItem, value: int) -> ItemRating:
    """Upsert the caller's verdict on a movie in a list.

    SELECT-then-INSERT/UPDATE with an IntegrityError fallback, not an ON CONFLICT
    upsert: SQLAlchemy has no dialect-neutral form of that and this suite runs on
    both Postgres and SQLite. Same shape as add_item's race handling.

    Re-sending the verdict you already hold is a no-op and does **not** move
    `rated_at` — the opinion didn't change, so neither did when you formed it.
    """
    existing = get_rating(db, item.id, user.id)
    if existing is not None:
        if existing.value != value:
            existing.value = value
            existing.rated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
        return existing

    rating = ItemRating(list_item_id=item.id, user_id=user.id, value=value)
    db.add(rating)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with the same user rating from another device/tab.
        db.rollback()
        existing = get_rating(db, item.id, user.id)
        if existing is None:
            raise
        existing.value = value
        existing.rated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    db.refresh(rating)
    return rating


def clear_rating(db: Session, *, user: User, item: ListItem) -> None:
    """Drop the caller's verdict. Idempotent — clearing an unrated movie is fine,
    because the client can't always know whether one exists and "it isn't rated"
    is the requested end state either way."""
    rating = get_rating(db, item.id, user.id)
    if rating is None:
        return
    db.delete(rating)
    db.commit()
