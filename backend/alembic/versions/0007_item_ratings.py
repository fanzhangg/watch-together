"""M8: item_ratings — one member's thumbs up/down on one movie in one list

Purely additive: a new table, no existing table touched, no backfill. Unlike
M7's watched_at -> watched_on cast (0006), there is no data to lose and
downgrade is a clean drop.

Scoped to the list item rather than to the film globally (docs/design.md §12).
The FK into list_items is what makes the privacy property structural: list_items
carries list_id, and every route already gates on membership of that list, so a
verdict cannot reach outside the list it was made in. The cascade also means
removing a movie takes the opinions about it along.

There is deliberately no constraint tying a verdict to the item's watch status;
they are independent facts with different owners.

Revision ID: 0007_item_ratings
Revises: 0006_watched_on
Create Date: 2026-07-25
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_item_ratings"
down_revision: str | None = "0006_watched_on"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK_NAME = "ck_item_ratings_value"


def upgrade() -> None:
    op.create_table(
        "item_ratings",
        sa.Column("list_item_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column(
            "rated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["list_item_id"], ["list_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        # list_item_id leads: reads are item-first, so this index serves them
        # and no secondary index is needed.
        sa.PrimaryKeyConstraint("list_item_id", "user_id"),
        sa.CheckConstraint("value IN (-1, 1)", name=CHECK_NAME),
    )


def downgrade() -> None:
    op.drop_table("item_ratings")
