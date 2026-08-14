"""
services/scheduler_service.py
──────────────────────────────
Periodic task that checks whether any guild is due for a scheduled report.

Design
──────
• Runs every 1 minute using ``discord.ext.tasks``.
• Does NOT hard-code a single daily time — each guild configures its own
  ``report_time`` and ``timezone``, so the scheduler compares the current
  local time of each guild against its own setting.
• Deduplication via ``ReportRepository`` prevents double-sends on restarts
  or if the loop fires twice within the same minute.

Scheduler lifecycle::

    scheduler = SchedulerService(bot, analytics)
    scheduler.start()   # called in setup_hook → after bot is ready
    scheduler.stop()    # called in on_close
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from discord.ext import tasks
from zoneinfo import ZoneInfo

import discord

from database.repositories import ReportRepository
from services.analytics_service import AnalyticsService
from services.report_service import ReportService

log = logging.getLogger(__name__)


class SchedulerService:
    """
    Drives periodic report delivery for all configured guilds.

    Attributes:
        bot:       The Discord client (needed to fetch channels).
        analytics: AnalyticsService for reading guild settings and stats.
    """

    def __init__(self, bot: discord.Client, analytics: AnalyticsService) -> None:
        self._bot = bot
        self._analytics = analytics
        self._report_service = ReportService(bot, analytics)
        self._report_repo = ReportRepository()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background loop (idempotent)."""
        if not self._loop.is_running():
            self._loop.start()
            log.info("Scheduler started.")

    def stop(self) -> None:
        """Cancel the background loop (idempotent)."""
        if self._loop.is_running():
            self._loop.cancel()
            log.info("Scheduler stopped.")

    # ── Loop ───────────────────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def _loop(self) -> None:
        """
        Called every minute.

        For each guild with a configured stats channel, check whether:
        - The current local time matches the guild's ``report_time``.
        - The appropriate report (daily / weekly) should fire.
        - The report has NOT already been delivered today (dedup).
        """
        settings_list = await self._analytics.guild_settings_for_reports()

        for settings in settings_list:
            try:
                await self._process_guild(settings)
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "Unhandled error processing scheduler for guild %s: %s",
                    settings.guild_id,
                    exc,
                )

    @_loop.before_loop
    async def _before_loop(self) -> None:
        """Wait until the Discord bot is fully ready before the loop starts."""
        await self._bot.wait_until_ready()

    # ── Per-guild logic ────────────────────────────────────────────────────────

    async def _process_guild(self, settings) -> None:  # type: ignore[no-untyped-def]
        """Check and optionally deliver daily and/or weekly reports for one guild."""
        now = datetime.now(ZoneInfo(settings.timezone))
        current_time_str = now.strftime("%H:%M")

        # If we have reached today's report time, the report covers yesterday.
        # If we haven't reached it yet, the report should cover the day before yesterday.
        # This prevents skipping a day entirely if the bot restarts across midnight.
        if current_time_str >= settings.report_time:
            period_end = (now - timedelta(days=1)).date()
        else:
            period_end = (now - timedelta(days=2)).date()

        guild_id = int(settings.guild_id)
        channel_id = int(settings.stats_channel_id)

        # 1. Process Daily Report if enabled
        if settings.daily_enabled:
            if not await self._report_repo.already_delivered(guild_id, "daily", period_end):
                success = await self._report_service.deliver(
                    guild_id, channel_id, "daily", period_end
                )
                if success:
                    await self._report_repo.mark_delivered(guild_id, "daily", period_end)

        # 2. Process Weekly Report if enabled and today is Monday (weekday == 0)
        if settings.weekly_enabled and now.weekday() == 0:
            if not await self._report_repo.already_delivered(guild_id, "weekly", period_end):
                success = await self._report_service.deliver(
                    guild_id, channel_id, "weekly", period_end
                )
                if success:
                    await self._report_repo.mark_delivered(guild_id, "weekly", period_end)

