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

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

__all__ = ["Base", "User"]


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
