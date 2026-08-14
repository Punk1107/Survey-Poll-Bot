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


@pytest.mark.asyncio
async def test_get_settings_auto_registers_unregistered_guild():
    """get_settings() and update_settings() should auto-register missing guilds on demand."""
    from services.analytics_service import AnalyticsService

    svc = AnalyticsService()
    settings = await svc.get_settings(99999)
    assert settings.guild_id == "99999"

    await svc.update_settings(99999, report_time="12:00")
    updated = await svc.get_settings(99999)
    assert updated.report_time == "12:00"


@pytest.mark.asyncio
async def test_repository_with_explicit_session():
    """Repositories should work correctly when given an existing session."""
    from database.connection import get_session
    from database.repositories import UserRepository, ChannelRepository

    await _seed_message(user_id=100, display_name="Alice")
    user_repo = UserRepository()
    chan_repo = ChannelRepository()

    async with get_session() as session:
        active = await user_repo.active_count(1, date(2025, 1, 1), date(2025, 1, 1), session=session)
        assert active == 1

        top = await chan_repo.top_channel(1, date(2025, 1, 1), date(2025, 1, 1), session=session)
        assert top == "general"

        total_u = await user_repo.total_messages(1, 100, date(2025, 1, 1), date(2025, 1, 1), session=session)
        assert total_u == 1

        total_c = await chan_repo.total_messages(1, 10, date(2025, 1, 1), date(2025, 1, 1), session=session)
        assert total_c == 1

        lb = await user_repo.leaderboard(1, date(2025, 1, 1), date(2025, 1, 1), limit=5, session=session)
        assert len(lb) == 1
        assert lb[0][0] == "Alice"


@pytest.mark.asyncio
async def test_activity_service_member_join_and_leave():
    """ActivityService should record member joins and leaves accurately."""
    from services.activity_service import ActivityService
    from services.analytics_service import AnalyticsService

    act_svc = ActivityService()
    await act_svc.record_member_join(guild_id=1, guild_name="Test", member_count=11)
    await act_svc.record_member_leave(guild_id=1, guild_name="Test", member_count=10)

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()

    analytics = AnalyticsService()
    summary = await analytics.summary(1, today, today)
    assert summary["new_members"] == 1
    assert summary["left_members"] == 1
