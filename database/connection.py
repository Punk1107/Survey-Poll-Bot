"""
database/connection.py
──────────────────────
SQLite connection management for the analytics database.

Responsibilities:
  • Create the async SQLAlchemy engine with the correct aiosqlite driver.
  • Apply SQLite PRAGMAs (WAL, foreign keys, busy timeout, …) on first connect.
  • Provide ``get_session()`` — the single entry point for all database I/O.

All other modules should import from here (or via ``database.__init__``):

    from database import get_session, engine
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import config

log = logging.getLogger(__name__)

# ── URL normalisation ──────────────────────────────────────────────────────────
# Support both bare "sqlite:///" and "sqlite+aiosqlite:///" in DATABASE_URL.
_raw_url: str = config.DATABASE_URL

if _raw_url.startswith("sqlite+aiosqlite://"):
    _async_url = _raw_url
elif _raw_url.startswith("sqlite:///"):
    _async_url = _raw_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
elif _raw_url.startswith("sqlite://"):
    _async_url = _raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
else:
    # PostgreSQL or other async-compatible URL — pass through untouched
    _async_url = _raw_url

_is_sqlite: bool = _async_url.startswith("sqlite+aiosqlite")

# ── Engine ─────────────────────────────────────────────────────────────────────
# SQLite: use StaticPool (single shared connection) to avoid WAL + multiple
# connections "database is locked" errors in a single-process asyncio app.
_engine_kwargs: dict = {"echo": False}

if _is_sqlite:
    _engine_kwargs.update(
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    )
else:
    _engine_kwargs["pool_pre_ping"] = True  # recover from stale connections

engine = create_async_engine(_async_url, **_engine_kwargs)


# ── SQLite PRAGMAs ─────────────────────────────────────────────────────────────
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
        """
        Applied once per physical SQLite connection (StaticPool → effectively once).

        WAL mode          — better concurrent read/write throughput.
        foreign_keys=ON   — enforce referential integrity at the DB level.
        synchronous=NORMAL — safe and faster than FULL.
        cache_size=-32000 — 32 MB page cache.
        temp_store=MEMORY — keep temp tables in RAM.
        busy_timeout=5000 — wait 5 s instead of raising "database is locked".
        mmap_size          — 128 MB memory-mapped I/O.
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-32000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA mmap_size=134217728")
        cursor.close()


# ── Session factory ────────────────────────────────────────────────────────────
_AsyncSessionFactory = sessionmaker(  # type: ignore[call-overload]
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager providing a scoped ``AsyncSession``.

    Commits on success, rolls back on any exception, always closes.

    Usage::

        async with get_session() as session:
            result = await session.execute(...)
    """
    session: AsyncSession = _AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
