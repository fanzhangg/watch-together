"""ORM models.

Types are chosen to be portable across Postgres (prod/Neon) and SQLite (local
dev/tests): ``Uuid`` stores natively on Postgres and as CHAR(32) on SQLite, and
``DateTime(timezone=True)`` maps to timestamptz / ISO strings respectively.
Tables land per milestone (users in M1; lists/members/items/invites in M2-M4)
per docs/design.md.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

__all__ = [
    "Base",
    "User",
    "List",
    "ListMember",
    "ListItem",
    "Invite",
    "ItemRating",
    "ROLE_OWNER",
    "ROLE_MEMBER",
    "STATUS_WANT",
    "STATUS_WATCHED",
    "STATUSES",
    "RATING_UP",
    "RATING_DOWN",
    "RATING_VALUES",
]

ROLE_OWNER = "owner"
ROLE_MEMBER = "member"

STATUS_WANT = "want_to_watch"
STATUS_WATCHED = "watched"
STATUSES = (STATUS_WANT, STATUS_WATCHED)

RATING_UP = 1
RATING_DOWN = -1
RATING_VALUES = (RATING_DOWN, RATING_UP)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # google_sub is null for the local dev-login user; unique otherwise.
    google_sub: Mapped[str | None] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class List(Base):
    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ListMember(Base):
    __tablename__ = "list_members"

    list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lists.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default=ROLE_MEMBER)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Invite(Base):
    """A shareable code that lets whoever opens it join a list.

    Multi-use until it expires (expires_at NULL = never). The code itself is the
    secret, so it must be generated with a CSPRNG — never a guessable sequence.
    """

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lists.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ListItem(Base):
    """A movie in a list, with a snapshot of its TMDB metadata.

    The snapshot means rendering a list needs zero TMDB calls (and survives TMDB
    outages); tmdb_id allows refreshing later. UNIQUE(list_id, tmdb_id) stops the
    same film being added twice to one list.
    """

    __tablename__ = "list_items"
    __table_args__ = (
        UniqueConstraint("list_id", "tmdb_id", name="uq_list_items_list_tmdb"),
        Index("ix_list_items_list_id", "list_id"),
        # Chronological ordering of the watched section.
        Index("ix_list_items_list_watched_on", "list_id", "watched_on"),
        # "Watched" and "has a date" are the same fact — enforced here so no
        # code path anywhere has to handle a watched-but-undated movie.
        CheckConstraint(
            "(status = 'watched') = (watched_on IS NOT NULL)",
            name="ck_list_items_watched_on_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lists.id", ondelete="CASCADE"), nullable=False
    )
    tmdb_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- TMDB snapshot ---
    title: Mapped[str] = mapped_column(String, nullable=False)
    release_year: Mapped[int | None] = mapped_column(Integer)
    poster_path: Mapped[str | None] = mapped_column(String)
    overview: Mapped[str | None] = mapped_column(String)

    status: Mapped[str] = mapped_column(String, nullable=False, default=STATUS_WANT)
    added_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The DAY it was watched, not an instant: "we watched it on the 12th" is the
    # same fact in every timezone, whereas a timestamp forces every reader to
    # pick one and gets the day wrong for an evening viewing. Null iff not watched.
    watched_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ItemRating(Base):
    """One member's verdict on one movie in one list — thumbs up or down (M8).

    Scoped to the **list item**, not to the film globally: a thumb is a social
    gesture aimed at the people in that list, so it stays inside it. Rate the
    same film in two different lists and those are two separate, unrelated
    remarks — which is what you'd expect of something said in two different
    rooms.

    That scope makes privacy **structural** rather than a query convention. The
    FK below is inside `list_items`, which carries `list_id`, which every route
    already gates on membership — so a verdict cannot physically reach someone
    outside the list, whatever a future query gets wrong. It also means a
    verdict dies with the movie: remove the film and the opinions about it go
    with it, instead of ambushing you when someone re-adds it a year later.

    **Nothing ties this to the item's watch status**, deliberately — see
    docs/design.md §12. A watch status belongs to the list ("we watched it"); a
    verdict belongs to a person ("I liked it"). Because no invariant spans the
    two, no member's action can invalidate another member's data, and the
    earlier drafts' unanswerable question ("someone un-watched a film you rated
    — now what?") simply doesn't arise.
    """

    __tablename__ = "item_ratings"
    __table_args__ = (
        # Two values, no null, no zero. "No opinion" is the absence of a row,
        # so this stays total rather than growing a third meaning.
        CheckConstraint("value IN (-1, 1)", name="ck_item_ratings_value"),
    )

    # list_item_id leads the primary key because every read is item-first
    # ("verdicts on these 40 movies"), so the PK index serves them directly and
    # no secondary index is needed.
    list_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("list_items.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    value: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Nothing reads this in M8. It's here because it cannot be backfilled: without
    # it, "what did we think of this last year" is unanswerable forever. It also
    # dates a verdict relative to list_items.watched_on, which is what a future
    # "Fang liked this *before* watching it" label would need.
    rated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
