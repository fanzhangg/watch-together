"""list_items (movies with TMDB snapshot)

Revision ID: 0004_list_items
Revises: 0003_lists
Create Date: 2026-07-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_list_items"
down_revision: str | None = "0003_lists"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "list_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("poster_path", sa.String(), nullable=True),
        sa.Column("overview", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("added_by", sa.Uuid(), nullable=False),
        sa.Column("watched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["list_id"], ["lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("list_id", "tmdb_id", name="uq_list_items_list_tmdb"),
    )
    op.create_index("ix_list_items_list_id", "list_items", ["list_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_list_items_list_id", table_name="list_items")
    op.drop_table("list_items")
