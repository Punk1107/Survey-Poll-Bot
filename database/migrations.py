"""
database/migrations.py
──────────────────────
Schema version management for the analytics database.

Design
──────
Each migration is a plain function ``migration_vN()`` that receives an active
``AsyncConnection``.  The ``MIGRATIONS`` list maps version numbers to functions.
The current schema version is stored in the SQLite ``user_version`` PRAGMA.

On every startup ``run_migrations()`` is called.  It reads the current version,
runs every pending migration in order, and updates the version PRAGMA once each
migration succeeds.  The process is idempotent — already-applied migrations are
skipped automatically.

Adding a new migration
──────────────────────
1. Write a new ``async def migration_vN(conn)`` function.
2. Append it to the ``MIGRATIONS`` list.

That's it — no manual version bumping, no DROP statements needed.
"""

from __future__ import annotations

import logging
from typing import Callable, Awaitable

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection

from .connection import engine

log = logging.getLogger(__name__)

MigrationFn = Callable[[AsyncConnection], Awaitable[None]]


async def _table_exists(conn: AsyncConnection, table_name: str) -> bool:
    """Return True when table_name exists for the current SQL dialect."""
    return await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table(table_name))


async def _get_schema_version(conn: AsyncConnection) -> int:
    """Read schema version from SQLite PRAGMA or a portable migrations table."""
    if conn.dialect.name == "sqlite":
        result = await conn.execute(text("PRAGMA user_version"))
        return int(result.scalar_one())

    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    result = await conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations"))
    return int(result.scalar_one() or 0)


async def _set_schema_version(conn: AsyncConnection, version: int) -> None:
    """Persist schema version for the current SQL dialect."""
    if conn.dialect.name == "sqlite":
        await conn.execute(text(f"PRAGMA user_version = {version}"))
        return

    await conn.execute(
        text("INSERT INTO schema_migrations (version) VALUES (:version) ON CONFLICT (version) DO NOTHING"),
        {"version": version},
    )


# ── Individual migrations ──────────────────────────────────────────────────────

async def migration_v1(conn: AsyncConnection) -> None:
    """
    V1 — initial analytics schema.

    Creates all analytics tables if they do not already exist.
    This migration is the baseline; the ORM ``create_all`` handles the actual
    DDL, so this function is intentionally a no-op — it just marks the baseline.
    """
    # Tables are created by Base.metadata.create_all in bot setup_hook.
    # This migration exists so that databases that went through create_all
    # are correctly recorded as being at v1.
    log.debug("Migration v1: baseline analytics schema (no-op)")


async def migration_v2(conn: AsyncConnection) -> None:
    """
    V2 — add ``analytics_report_deliveries`` table if missing.

    Idempotent: checks PRAGMA table_info before executing DDL.
    """
    if not await _table_exists(conn, "analytics_report_deliveries"):
        await conn.execute(text("""
            CREATE TABLE analytics_report_deliveries (
                guild_id    TEXT NOT NULL,
                report_type TEXT NOT NULL,
                period_end  DATE NOT NULL,
                PRIMARY KEY (guild_id, report_type, period_end)
            )
        """))
        log.info("Migration v2: created analytics_report_deliveries table")


async def migration_v3(conn: AsyncConnection) -> None:
    """
    V3 - add high-volume analytics indexes.

    These indexes keep the hot API/report queries fast as guilds, users,
    channels, and daily/hourly stat rows grow across many Discord servers.
    """
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_daily_guild_stats_period ON daily_guild_stats (guild_id, date)",
        "CREATE INDEX IF NOT EXISTS ix_hourly_guild_stats_period ON hourly_guild_stats (guild_id, date, hour)",
        "CREATE INDEX IF NOT EXISTS ix_daily_user_stats_period_user ON daily_user_stats (guild_id, date, user_id)",
        "CREATE INDEX IF NOT EXISTS ix_daily_channel_stats_period_channel ON daily_channel_stats (guild_id, date, channel_id)",
    ]
    for statement in statements:
        await conn.execute(text(statement))


async def migration_v4(conn: AsyncConnection) -> None:
    """
    V4 — fix incorrect index columns on ``daily_user_stats`` and ``daily_channel_stats``.

    The original indexes (``ix_daily_user_stats_lookup`` and
    ``ix_daily_channel_stats_lookup``) mistakenly included the ``messages`` column
    as the third key.  ``messages`` is a value column — it is never used in WHERE
    predicates — so the index was providing no benefit on queries while adding
    write overhead on every message event.

    This migration drops the old indexes and recreates them with the correct
    columns (``user_id`` and ``channel_id``) that are actually referenced in
    JOIN and WHERE clauses.
    """
    # Drop old (incorrect) indexes — IF EXISTS makes this idempotent.
    await conn.execute(text("DROP INDEX IF EXISTS ix_daily_user_stats_lookup"))
    await conn.execute(text("DROP INDEX IF EXISTS ix_daily_channel_stats_lookup"))

    # Recreate with correct columns.
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_daily_user_stats_lookup "
        "ON daily_user_stats (guild_id, date, user_id)"
    ))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_daily_channel_stats_lookup "
        "ON daily_channel_stats (guild_id, date, channel_id)"
    ))
    log.info("Migration v4: rebuilt daily_user_stats and daily_channel_stats indexes")


async def migration_v5(conn: AsyncConnection) -> None:
    """
    V5 — add missing columns to the ``surveys`` and ``questions`` tables.

    These columns were added to the ORM model after the initial release.
    ``Base.metadata.create_all`` never adds columns to *existing* tables, so
    databases created before these columns were introduced will be missing them.

    This migration is idempotent: it checks the existing column list via
    ``PRAGMA table_info`` before issuing any ``ALTER TABLE`` statement.

    Columns added to ``surveys``:
      - ``description``    TEXT (nullable)
      - ``max_responses``  INTEGER (nullable)
      - ``is_active``      BOOLEAN NOT NULL DEFAULT 1

    Columns added to ``questions``:
      - ``order``          INTEGER NOT NULL DEFAULT 0
    """
    async def _existing_columns(table: str) -> set[str]:
        """Return the set of column names for *table* (works on SQLite & PostgreSQL)."""
        def _get_cols(sync_conn):
            insp = inspect(sync_conn)
            if not insp.has_table(table):
                return set()
            return {c["name"] for c in insp.get_columns(table)}
        return await conn.run_sync(_get_cols)

    surveys_cols = await _existing_columns("surveys")
    if "description" not in surveys_cols:
        await conn.execute(text("ALTER TABLE surveys ADD COLUMN description TEXT"))
        log.info("Migration v5: added column surveys.description")
    if "max_responses" not in surveys_cols:
        await conn.execute(text("ALTER TABLE surveys ADD COLUMN max_responses INTEGER"))
        log.info("Migration v5: added column surveys.max_responses")
    if "is_active" not in surveys_cols:
        bool_col_type = "BOOLEAN DEFAULT TRUE" if conn.dialect.name != "sqlite" else "BOOLEAN NOT NULL DEFAULT 1"
        await conn.execute(text(f"ALTER TABLE surveys ADD COLUMN is_active {bool_col_type}"))
        log.info("Migration v5: added column surveys.is_active")

    questions_cols = await _existing_columns("questions")
    if "order" not in questions_cols:
        await conn.execute(text('ALTER TABLE questions ADD COLUMN "order" INTEGER NOT NULL DEFAULT 0'))
        log.info("Migration v5: added column questions.order")


async def migration_v6(conn: AsyncConnection) -> None:
    """
    V6 — enable reports for guilds that already have a channel configured.

    The original schema defaulted ``daily_enabled`` and ``weekly_enabled`` to
    ``False``.  This meant that admins who ran ``/config stats-channel`` but
    never explicitly ran ``/config daily on`` and ``/config weekly on`` received
    no reports at all — silently.

    This migration flips both flags to ``True`` for every ``guild_settings`` row
    that already has a ``stats_channel_id`` set, matching the admin's clear intent
    when they configured a channel.  Guilds with no channel configured are left
    untouched (no point enabling reports with nowhere to send them).
    """
    result = await conn.execute(text("""
        UPDATE guild_settings
        SET daily_enabled = TRUE, weekly_enabled = TRUE
        WHERE stats_channel_id IS NOT NULL
          AND (daily_enabled = FALSE OR daily_enabled IS NULL)
          AND (weekly_enabled = FALSE OR weekly_enabled IS NULL)
    """))
    rows_updated = result.rowcount
    if rows_updated:
        log.info(
            "Migration v6: enabled reports for %d guild(s) that already had a stats channel configured",
            rows_updated,
        )


# ── Migration registry ─────────────────────────────────────────────────────────
# Order matters — migrations run in list order, one per version increment.
MIGRATIONS: list[MigrationFn] = [
    migration_v1,   # version 1
    migration_v2,   # version 2
    migration_v3,   # version 3
    migration_v4,   # version 4
    migration_v5,   # version 5
    migration_v6,   # version 6
]


# ── Runner ─────────────────────────────────────────────────────────────────────

async def run_migrations() -> None:
    """
    Apply all pending analytics-schema migrations in version order.

    Reads the current ``user_version`` PRAGMA, runs every migration whose
    index (0-based) is >= current version, then bumps the PRAGMA.
    """
    async with engine.begin() as conn:
        current_version = await _get_schema_version(conn)
        log.debug("Database schema version = %d, available migrations = %d", current_version, len(MIGRATIONS))

        for idx, migration_fn in enumerate(MIGRATIONS):
            version = idx + 1  # 1-based
            if version <= current_version:
                continue  # already applied
            log.info("Applying migration v%d (%s)…", version, migration_fn.__name__)
            await migration_fn(conn)
            await _set_schema_version(conn, version)
            log.info("Migration v%d applied successfully.", version)
