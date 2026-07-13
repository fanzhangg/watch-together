"""Pydantic schemas (API request/response shapes)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


class GoogleLoginIn(BaseModel):
    # The `credential` JWT returned by Google Identity Services on the client.
    credential: str


class ConfigOut(BaseModel):
    """Public, non-secret runtime config the SPA needs to render the login page."""

    # Null when no OAuth client is configured -> no Google button.
    google_client_id: str | None = None
    # False in production -> the login page must not offer the dev bypass.
    dev_login: bool = False


# --- Lists ---------------------------------------------------------------
class ListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ListUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserOut
    role: str


class ListOut(BaseModel):
    """A list as it appears in the caller's collection, with their own role."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime
    role: str


class ListDetail(ListOut):
    members: list[MemberOut]


# --- Movies / list items -------------------------------------------------
Status = Literal["want_to_watch", "watched"]


class MovieSearchResult(BaseModel):
    """A trimmed TMDB search hit — never the raw TMDB payload."""

    model_config = ConfigDict(from_attributes=True)

    tmdb_id: int
    title: str
    release_year: int | None = None
    poster_path: str | None = None
    overview: str | None = None


class MovieDetail(BaseModel):
    """Full TMDB metadata for the movie detail page — fetched live, not stored."""

    model_config = ConfigDict(from_attributes=True)

    tmdb_id: int
    title: str
    release_year: int | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    overview: str | None = None
    tagline: str | None = None
    runtime: int | None = None  # minutes
    genres: list[str] = []
    vote_average: float | None = None
    director: str | None = None
    cast: list[str] = []


class ItemCreate(BaseModel):
    tmdb_id: int
    status: Status = "want_to_watch"


# A client's "today" can legitimately be a day ahead of the server's (they send
# their LOCAL date; the server thinks in UTC). Tolerate exactly that much and no
# more — you cannot have watched a film next week.
FUTURE_TOLERANCE_DAYS = 1


class ItemUpdate(BaseModel):
    """Change a movie's watched status and/or the day it was watched.

    Both fields are optional but at least one is required. Contradictions are
    rejected rather than silently repaired — they can only come from a client
    bug, and the DB CHECK would reject them anyway. `model_fields_set` is what
    distinguishes "watched_on omitted" (leave it alone) from an explicit
    `"watched_on": null` (blank it — which is never allowed while watched).
    """

    status: Status | None = None
    watched_on: date | None = None

    @field_validator("watched_on")
    @classmethod
    def _not_in_the_future(cls, value: date | None) -> date | None:
        if value is None:
            return value
        limit = datetime.now(timezone.utc).date() + timedelta(days=FUTURE_TOLERANCE_DAYS)
        if value > limit:
            raise ValueError("watched_on cannot be in the future")
        return value

    @model_validator(mode="after")
    def _coherent(self) -> ItemUpdate:
        if not self.model_fields_set:
            raise ValueError("provide status and/or watched_on")
        if self.status == "want_to_watch" and self.watched_on is not None:
            raise ValueError("an unwatched movie cannot have a watch date")
        return self

    @property
    def sets_watched_on(self) -> bool:
        """True when the caller sent the field at all — including as null."""
        return "watched_on" in self.model_fields_set


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tmdb_id: int
    title: str
    release_year: int | None = None
    poster_path: str | None = None
    overview: str | None = None
    status: Status
    added_by: uuid.UUID
    # Null iff status is want_to_watch — the DB CHECK guarantees it.
    watched_on: date | None = None
    created_at: datetime


# --- Invites -------------------------------------------------------------
class InviteCreate(BaseModel):
    # Optional lifetime. Omit for a link that never expires.
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class InviteOut(BaseModel):
    code: str
    url: str
    list_id: uuid.UUID
    expires_at: datetime | None = None


class InvitePreview(BaseModel):
    """Shown before accepting, so you know what you're joining."""

    code: str
    list_name: str
    invited_by: str
    expires_at: datetime | None = None
