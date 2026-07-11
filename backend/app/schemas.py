"""Pydantic schemas (API request/response shapes)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None


class GoogleLoginIn(BaseModel):
    # The `credential` JWT returned by Google Identity Services on the client.
    credential: str
