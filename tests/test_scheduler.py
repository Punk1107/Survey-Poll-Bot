"""
tests/test_scheduler.py
────────────────────────
Tests for SchedulerService and ReportService delivery.
Covers:
  - Channel fetch fallback when bot.get_channel returns None.
  - Report deduplication marking occurring only AFTER delivery succeeds.
  - Independent Daily and Weekly report delivery processing.
  - Calculation of prior week's stats for Weekly Report WoW comparison.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from zoneinfo import ZoneInfo

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


@pytest.mark.asyncio
async def test_report_service_channel_fetch_fallback():
    """ReportService should try fetch_channel if get_channel returns None."""
    from services.analytics_service import AnalyticsService
    from services.report_service import ReportService

    bot = MagicMock()
    bot.get_channel.return_value = None

    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock()
    bot.fetch_channel = AsyncMock(return_value=mock_channel)

    analytics = AnalyticsService()

    svc = ReportService(bot, analytics)
    success = await svc.deliver(12345, 99999, "daily", date(2025, 1, 1))

    assert success is True
    bot.fetch_channel.assert_called_once_with(99999)
    mock_channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_report_service_weekly_wow_calculation():
    """ReportService should include prev_messages for weekly reports."""
    from services.analytics_service import AnalyticsService
    from services.report_service import ReportService
    from database.repositories import ActivityRepository, GuildRepository

    guild_repo = GuildRepository()
    act_repo = ActivityRepository()

    await guild_repo.upsert(1, "Test Guild", 10)
    # Seed messages in prior week (Dec 25 - Dec 31)
    for _ in range(5):
        await act_repo.record_message(
            guild_id=1,
            channel_id=10,
            user_id=100,
            display_name="Alice",
            channel_name="general",
            day=date(2024, 12, 28),
            hour=12,
        )
    # Seed messages in current week (Jan 1 - Jan 7)
    for _ in range(10):
        await act_repo.record_message(
            guild_id=1,
            channel_id=10,
            user_id=100,
            display_name="Alice",
            channel_name="general",
            day=date(2025, 1, 4),
            hour=12,
        )


    bot = MagicMock()
    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    analytics = AnalyticsService()
    svc = ReportService(bot, analytics)

    success = await svc.deliver(1, 10, "weekly", date(2025, 1, 7))
    assert success is True

    # Check embed sent to channel
    sent_embed = mock_channel.send.call_args.kwargs["embed"]
    assert "Weekly Report" in sent_embed.title
    # Check messages field contains WoW percentage (10 vs 5 -> +100%)
    messages_field = next(field.value for field in sent_embed.fields if "Messages" in field.name)
    assert "+100.0%" in messages_field



@pytest.mark.asyncio
async def test_scheduler_marks_delivered_only_on_success():
    """SchedulerService must NOT mark delivered if deliver() returns False."""
    from services.analytics_service import AnalyticsService
    from services.scheduler_service import SchedulerService
    from database.repositories import GuildRepository, ReportRepository

    guild_repo = GuildRepository()
    await guild_repo.upsert(123, "Test Guild", 10)
    await guild_repo.update_settings(
        123,
        stats_channel_id="999",
        daily_enabled=True,
        report_time="00:00",
        timezone="UTC",
    )

    bot = MagicMock()
    bot.get_channel.return_value = None
    bot.fetch_channel = AsyncMock(side_effect=Exception("Discord API error"))

    analytics = AnalyticsService()
    scheduler = SchedulerService(bot, analytics)

    # Process guild -> deliver should fail because fetch_channel raises Exception
    settings = await analytics.get_settings(123)
    await scheduler._process_guild(settings)

    # Check that report repository does NOT have it marked as delivered
    report_repo = ReportRepository()
    delivered = await report_repo.already_delivered(123, "daily", date.today())
    assert delivered is False
