"""ORM models.

M0 defines only the declarative ``Base`` and re-exports it. Tables (users,
lists, list_members, list_items, invites) are added in later milestones
(M1/M2/M3/M4) per docs/design.md, each with its own Alembic migration.
"""

from __future__ import annotations

from app.db import Base

__all__ = ["Base"]
