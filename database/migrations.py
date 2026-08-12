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


# ── Migration registry ─────────────────────────────────────────────────────────
# Order matters — migrations run in list order, one per version increment.
MIGRATIONS: list[MigrationFn] = [
    migration_v1,   # version 1
    migration_v2,   # version 2
    migration_v3,   # version 3
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
