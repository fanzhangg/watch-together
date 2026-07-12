"""ORM models.

Types are chosen to be portable across Postgres (prod/Neon) and SQLite (local
dev/tests): ``Uuid`` stores natively on Postgres and as CHAR(32) on SQLite, and
``DateTime(timezone=True)`` maps to timestamptz / ISO strings respectively.
Tables land per milestone (users in M1; lists/members/items/invites in M2-M4)
per docs/design.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    "ROLE_OWNER",
    "ROLE_MEMBER",
    "STATUS_WANT",
    "STATUS_WATCHED",
    "STATUSES",
]

ROLE_OWNER = "owner"
ROLE_MEMBER = "member"

STATUS_WANT = "want_to_watch"
STATUS_WATCHED = "watched"
STATUSES = (STATUS_WANT, STATUS_WATCHED)


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
    watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
