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

        # IMPORTANT: @tasks.loop creates a *class-level* Loop object, not an
        # instance-level one.  If two SchedulerService instances were ever created
        # (e.g. during testing or a misconfigured hot-reload), they would share
        # the same Loop, causing stale-self bugs.
        #
        # We work around this by constructing a fresh per-instance Loop in
        # __init__ and wiring the before_loop hook explicitly.
        self._loop: tasks.Loop = tasks.loop(minutes=1)(self._tick)  # type: ignore[assignment]
        self._loop.before_loop(self._before_loop)

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

    async def _tick(self) -> None:
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

    async def _before_loop(self) -> None:
        """Wait until the Discord bot is fully ready before the loop starts."""
        await self._bot.wait_until_ready()

    # ── Per-guild logic ────────────────────────────────────────────────────────

    # How many minutes past the configured time we'll still attempt delivery.
    # This creates a catch-up window so the report fires even if the bot was
    # briefly down at the exact scheduled time.
    _CATCHUP_WINDOW_MINUTES: int = 5

    async def _process_guild(self, settings) -> None:  # type: ignore[no-untyped-def]
        """Check and optionally deliver daily and/or weekly reports for one guild."""

        # Guard: channel must be set before we do anything
        if not settings.stats_channel_id:
            return

        try:
            tz = ZoneInfo(settings.timezone)
        except Exception:
            log.warning(
                "Guild %s has invalid timezone %r — skipping scheduler",
                settings.guild_id,
                settings.timezone,
            )
            return

        now = datetime.now(tz)

        # Check if we're within the catch-up window of the configured report time.
        # This handles the common case where the bot was briefly down at the exact
        # scheduled minute — we'll still fire within the next N minutes.
        try:
            report_h, report_m = map(int, settings.report_time.split(":"))
        except (ValueError, AttributeError):
            log.warning(
                "Guild %s has invalid report_time %r — skipping scheduler",
                settings.guild_id,
                settings.report_time,
            )
            return

        now_total_minutes = now.hour * 60 + now.minute
        report_total_minutes = report_h * 60 + report_m
        minutes_past = now_total_minutes - report_total_minutes

        # Only fire within [0, CATCHUP_WINDOW_MINUTES) minutes after the configured time.
        # Negative means we haven't reached the time yet; too large means we already passed.
        if not (0 <= minutes_past < self._CATCHUP_WINDOW_MINUTES):
            return

        # The report covers the completed day *before* the fire time (i.e. yesterday).
        period_end = (now - timedelta(days=1)).date()

        guild_id = int(settings.guild_id)
        channel_id = int(settings.stats_channel_id)

        log.debug(
            "Scheduler fire: guild=%s report_time=%s now=%s period_end=%s daily=%s weekly=%s",
            guild_id,
            settings.report_time,
            now.strftime("%H:%M"),
            period_end,
            settings.daily_enabled,
            settings.weekly_enabled,
        )

        # 1. Daily report — fires every day if enabled
        if settings.daily_enabled:
            already = await self._report_repo.already_delivered(guild_id, "daily", period_end)
            if not already:
                # Mark delivered *before* sending to guard against races / retries.
                await self._report_repo.mark_delivered(guild_id, "daily", period_end)
                success = await self._report_service.deliver(
                    guild_id, channel_id, "daily", period_end
                )
                if not success:
                    log.warning(
                        "Daily report delivery failed for guild=%s period_end=%s",
                        guild_id,
                        period_end,
                    )
            else:
                log.debug("Daily report already delivered: guild=%s period_end=%s", guild_id, period_end)

        # 2. Weekly report — fires only on Monday (weekday == 0) if enabled
        if settings.weekly_enabled and now.weekday() == 0:
            already = await self._report_repo.already_delivered(guild_id, "weekly", period_end)
            if not already:
                await self._report_repo.mark_delivered(guild_id, "weekly", period_end)
                success = await self._report_service.deliver(
                    guild_id, channel_id, "weekly", period_end
                )
                if not success:
                    log.warning(
                        "Weekly report delivery failed for guild=%s period_end=%s",
                        guild_id,
                        period_end,
                    )
            else:
                log.debug("Weekly report already delivered: guild=%s period_end=%s", guild_id, period_end)

