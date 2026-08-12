"""
tests/test_analytics.py
─────────────────────────
Tests for AnalyticsService query logic.

Uses an in-memory SQLite database seeded with known data so tests are
deterministic and don't require a live Discord connection.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
import pytest_asyncio

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DISCORD_TOKEN", "test_token_placeholder")
os.environ.setdefault("DEFAULT_TIMEZONE", "UTC")


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    from database.connection import engine
    from models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed_message(
    guild_id: int = 1,
    guild_name: str = "Test",
    channel_id: int = 10,
    channel_name: str = "general",
    user_id: int = 100,
    display_name: str = "Alice",
    day: date = date(2025, 1, 1),
    hour: int = 12,
) -> None:
    from database.repositories import ActivityRepository, GuildRepository

    await GuildRepository().upsert(guild_id, guild_name, 10)
    await ActivityRepository().record_message(
        guild_id=guild_id,
        channel_id=channel_id,
        user_id=user_id,
        display_name=display_name,
        channel_name=channel_name,
        day=day,
        hour=hour,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summary_counts_messages():
    """summary() should count seeded messages correctly."""
    await _seed_message()
    await _seed_message()  # second message

    from services.analytics_service import AnalyticsService

    svc = AnalyticsService()
    result = await svc.summary(1, date(2025, 1, 1), date(2025, 1, 1))
    assert result["messages"] == 2


@pytest.mark.asyncio
async def test_summary_counts_active_users():
    """summary() should count distinct active users."""
    await _seed_message(user_id=100, display_name="Alice")
    await _seed_message(user_id=101, display_name="Bob")
    await _seed_message(user_id=100, display_name="Alice")  # Alice again

    from services.analytics_service import AnalyticsService

    svc = AnalyticsService()
    result = await svc.summary(1, date(2025, 1, 1), date(2025, 1, 1))
    assert result["active_users"] == 2


@pytest.mark.asyncio
async def test_leaderboard_order():
    """leaderboard() should rank users by message count descending."""
    for _ in range(3):
        await _seed_message(user_id=100, display_name="Alice")
    await _seed_message(user_id=101, display_name="Bob")

    from services.analytics_service import AnalyticsService

    svc = AnalyticsService()
    lb = await svc.leaderboard(1, date(2025, 1, 1), date(2025, 1, 1))
    assert lb[0][0] == "Alice"
    assert lb[0][1] == 3
    assert lb[1][0] == "Bob"
    assert lb[1][1] == 1


@pytest.mark.asyncio
async def test_summary_user_filter():
    """summary(user_id=X) should return only that user's messages."""
    await _seed_message(user_id=100, display_name="Alice")
    await _seed_message(user_id=100, display_name="Alice")
    await _seed_message(user_id=101, display_name="Bob")

    from services.analytics_service import AnalyticsService

    svc = AnalyticsService()
    result = await svc.summary(1, date(2025, 1, 1), date(2025, 1, 1), user_id=100)
    assert result["messages"] == 2
