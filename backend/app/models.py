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

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

__all__ = ["Base", "User", "List", "ListMember", "ROLE_OWNER", "ROLE_MEMBER"]

ROLE_OWNER = "owner"
ROLE_MEMBER = "member"


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
