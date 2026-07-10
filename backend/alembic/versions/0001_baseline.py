"""baseline (empty)

The M0 baseline establishes the migration chain. Tables are introduced in
later milestones (users in M1, lists/members in M2, etc.), each as its own
revision building on this one.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-10
"""
from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
