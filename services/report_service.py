"""
services/report_service.py
───────────────────────────
Assembles and delivers scheduled analytics reports to Discord channels.

Flow::

    SchedulerService
        ↓
    ReportService.deliver(guild_id, channel_id, report_type, period_end)
        ↓
    AnalyticsService.summary()       ← fetch data
        ↓
    reports.daily_report / weekly_report  ← build content
        ↓
    reports.embeds                   ← build Discord Embed
        ↓
    discord.TextChannel.send()       ← deliver

The dedup check (``ReportRepository``) is done *before* calling this service,
in ``SchedulerService``.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

import discord

from services.analytics_service import AnalyticsService
from reports.embeds import build_daily_embed, build_weekly_embed

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class ReportService:
    """Fetches analytics data and sends a formatted embed to a Discord channel."""

    def __init__(self, bot: discord.Client, analytics: AnalyticsService) -> None:
        self._bot = bot
        self._analytics = analytics

    async def deliver(
        self,
        guild_id: int,
        channel_id: int,
        report_type: str,
        period_end: date,
    ) -> bool:
        """
        Build and send a ``report_type`` report for the period ending on *period_end*.

        Args:
            guild_id:    Discord guild ID.
            channel_id:  Discord channel ID to send the report to.
            report_type: ``"daily"`` or ``"weekly"``.
            period_end:  The last date of the reporting period (exclusive — the
                         day *before* the report fires so yesterday's data is used).

        Returns:
            True on success, False if the channel was not found or send failed.
        """
        channel = self._bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning(
                "Cannot deliver %s report — channel %s not found or not a TextChannel",
                report_type,
                channel_id,
            )
            return False

        days = 7 if report_type == "weekly" else 1
        start = period_end - timedelta(days=days - 1)
        stats = await self._analytics.summary(guild_id, start, period_end)

        if report_type == "weekly":
            embed = build_weekly_embed(stats, start, period_end)
        else:
            embed = build_daily_embed(stats, period_end)

        try:
            await channel.send(embed=embed)
            log.info(
                "Delivered %s report to guild=%s channel=%s period_end=%s",
                report_type,
                guild_id,
                channel_id,
                period_end,
            )
            return True
        except discord.HTTPException as exc:
            log.warning(
                "Failed to send %s report to guild=%s channel=%s: %s",
                report_type,
                guild_id,
                channel_id,
                exc,
            )
            return False
