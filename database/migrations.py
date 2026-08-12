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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .connection import engine

log = logging.getLogger(__name__)

MigrationFn = Callable[[AsyncConnection], Awaitable[None]]


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
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_report_deliveries'")
    )
    if result.first() is None:
        await conn.execute(text("""
            CREATE TABLE analytics_report_deliveries (
                guild_id    TEXT NOT NULL,
                report_type TEXT NOT NULL,
                period_end  DATE NOT NULL,
                PRIMARY KEY (guild_id, report_type, period_end)
            )
        """))
        log.info("Migration v2: created analytics_report_deliveries table")


# ── Migration registry ─────────────────────────────────────────────────────────
# Order matters — migrations run in list order, one per version increment.
MIGRATIONS: list[MigrationFn] = [
    migration_v1,   # version 1
    migration_v2,   # version 2
]


# ── Runner ─────────────────────────────────────────────────────────────────────

async def run_migrations() -> None:
    """
    Apply all pending analytics-schema migrations in version order.

    Reads the current ``user_version`` PRAGMA, runs every migration whose
    index (0-based) is >= current version, then bumps the PRAGMA.
    """
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA user_version"))
        current_version: int = result.scalar_one()
        log.debug("Database user_version = %d, available migrations = %d", current_version, len(MIGRATIONS))

        for idx, migration_fn in enumerate(MIGRATIONS):
            version = idx + 1  # 1-based
            if version <= current_version:
                continue  # already applied
            log.info("Applying migration v%d (%s)…", version, migration_fn.__name__)
            await migration_fn(conn)
            await conn.execute(text(f"PRAGMA user_version = {version}"))
            log.info("Migration v%d applied successfully.", version)
