"""Pydantic schemas (API request/response shapes)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


class GoogleLoginIn(BaseModel):
    # The `credential` JWT returned by Google Identity Services on the client.
    credential: str


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


class ItemCreate(BaseModel):
    tmdb_id: int
    status: Status = "want_to_watch"


class ItemUpdate(BaseModel):
    status: Status


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
    watched_at: datetime | None = None
    created_at: datetime
