"""M7: watched_at (timestamptz) -> watched_on (date), backfilled

The watch date becomes a DATE the user owns rather than an instant the server
stamped. "We watched it on the 12th" is the same fact in every timezone; a
timestamp forces every reader to pick one.

THE BACKFILL IS LOSSY AND IRREVERSIBLE -- take a pg_dump first. The cast must
happen in the users' LOCAL zone, not UTC: a 9pm PDT viewing is stored as 04:00
UTC *the next day*, so a naive ::date would move every evening film forward a
day. Both users are US Pacific; if that ever stops being true, this constant is
the thing to revisit (it does not affect new rows -- the client sends its own
local date).

Revision ID: 0006_watched_on
Revises: 0005_invites
Create Date: 2026-07-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_watched_on"
down_revision: str | None = "0005_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WATCH_TZ = "America/Los_Angeles"
# SQLite (local dev.db) has no tz database. Pacific standard time is close
# enough for a throwaway dev database; prod is Postgres and does it properly.
SQLITE_TZ_OFFSET = "-8 hours"

CHECK_NAME = "ck_list_items_watched_on_matches_status"
INDEX_NAME = "ix_list_items_list_watched_on"


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"

    op.add_column("list_items", sa.Column("watched_on", sa.Date(), nullable=True))

    if postgres:
        op.execute(
            f"""
            UPDATE list_items
               SET watched_on = (watched_at AT TIME ZONE '{WATCH_TZ}')::date
             WHERE watched_at IS NOT NULL
            """
        )
        # Watched but never stamped (shouldn't exist, but the new CHECK would
        # reject it): fall back to the day it was added to the list.
        op.execute(
            f"""
            UPDATE list_items
               SET watched_on = (created_at AT TIME ZONE '{WATCH_TZ}')::date
             WHERE status = 'watched' AND watched_on IS NULL
            """
        )
    else:
        op.execute(
            "UPDATE list_items "
            f"SET watched_on = date(watched_at, '{SQLITE_TZ_OFFSET}') "
            "WHERE watched_at IS NOT NULL"
        )
        op.execute(
            "UPDATE list_items "
            f"SET watched_on = date(created_at, '{SQLITE_TZ_OFFSET}') "
            "WHERE status = 'watched' AND watched_on IS NULL"
        )

    # A stale date on an unwatched row would violate the invariant below.
    op.execute("UPDATE list_items SET watched_on = NULL WHERE status <> 'watched'")

    with op.batch_alter_table("list_items") as batch:
        batch.drop_column("watched_at")
        batch.create_check_constraint(
            CHECK_NAME, "(status = 'watched') = (watched_on IS NOT NULL)"
        )
    op.create_index(INDEX_NAME, "list_items", ["list_id", "watched_on"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"

    op.drop_index(INDEX_NAME, table_name="list_items")
    op.add_column(
        "list_items", sa.Column("watched_at", sa.DateTime(timezone=True), nullable=True)
    )

    # The time of day is gone for good; local midnight is the best we can do.
    if postgres:
        op.execute(
            f"""
            UPDATE list_items
               SET watched_at = watched_on::timestamp AT TIME ZONE '{WATCH_TZ}'
             WHERE watched_on IS NOT NULL
            """
        )
    else:
        op.execute(
            "UPDATE list_items SET watched_at = datetime(watched_on) "
            "WHERE watched_on IS NOT NULL"
        )

    with op.batch_alter_table("list_items") as batch:
        batch.drop_constraint(CHECK_NAME, type_="check")
        batch.drop_column("watched_on")
