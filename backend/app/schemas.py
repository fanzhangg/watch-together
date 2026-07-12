"""Pydantic schemas (API request/response shapes)."""

from __future__ import annotations

import uuid
from datetime import datetime

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
