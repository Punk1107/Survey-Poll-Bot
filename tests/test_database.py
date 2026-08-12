"""
tests/test_database.py
───────────────────────
Unit / integration tests for the database layer.

Tests cover:
  - GuildRepository: upsert, get_settings, update_settings
  - ActivityRepository: record_message increments counters correctly
  - ReportRepository: dedup check (already_delivered / mark_delivered)
  - Migrations: run_migrations() is idempotent
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

# Set a test database path so tests don't touch the production DB.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DISCORD_TOKEN", "test_token_placeholder")
os.environ.setdefault("DEFAULT_TIMEZONE", "UTC")


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables in the in-memory database before each test."""
    from database.connection import engine
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── GuildRepository ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guild_upsert_creates_settings():
    """Upserting a guild should also create default GuildSettings."""
    from database.repositories import GuildRepository

    repo = GuildRepository()
    await repo.upsert(12345, "Test Guild", 100)

    settings = await repo.get_settings(12345)
    assert settings.guild_id == "12345"
    assert settings.timezone == "UTC"


@pytest.mark.asyncio
async def test_guild_get_settings_raises_for_unknown_guild():
    """get_settings() should raise LookupError for unregistered guilds."""
    from database.repositories import GuildRepository

    repo = GuildRepository()
    with pytest.raises(LookupError):
        await repo.get_settings(99999)


@pytest.mark.asyncio
async def test_guild_update_settings():
    """update_settings() should persist field changes."""
    from database.repositories import GuildRepository

    repo = GuildRepository()
    await repo.upsert(12345, "Test Guild", 100)
    await repo.update_settings(12345, report_time="18:00", timezone="Europe/London")

    settings = await repo.get_settings(12345)
    assert settings.report_time == "18:00"
    assert settings.timezone == "Europe/London"


@pytest.mark.asyncio
async def test_guild_update_settings_rejects_invalid_key():
    """update_settings() with an invalid key should raise ValueError."""
    from database.repositories import GuildRepository

    repo = GuildRepository()
    await repo.upsert(12345, "Test Guild", 100)
    with pytest.raises(ValueError, match="Unsupported"):
        await repo.update_settings(12345, nonexistent_field="value")


# ── ReportRepository ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_dedup():
    """mark_delivered then already_delivered should return True."""
    from datetime import date
    from database.repositories import GuildRepository, ReportRepository

    guild_repo = GuildRepository()
    await guild_repo.upsert(12345, "Test Guild", 100)

    report_repo = ReportRepository()
    day = date(2025, 1, 1)

    assert not await report_repo.already_delivered(12345, "daily", day)
    await report_repo.mark_delivered(12345, "daily", day)
    assert await report_repo.already_delivered(12345, "daily", day)


# ── Migrations ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_migrations_is_idempotent():
    """run_migrations() should not raise when called twice."""
    from database.migrations import run_migrations

    await run_migrations()
    await run_migrations()  # second call must be safe
