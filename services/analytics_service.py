"""
services/analytics_service.py
──────────────────────────────
Read-only analytics queries — the "brains" of the bot.

Aggregates raw ``daily_*_stats`` rows into the summary dicts that commands
and reports consume.  No writes happen here.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from zoneinfo import ZoneInfo

from database.repositories import ChannelRepository, GuildRepository, UserRepository
from database.connection import get_session
from models import DailyGuildStat, HourlyGuildStat
from sqlalchemy import func, select, text
from utils.time import date_range

log = logging.getLogger(__name__)


class AnalyticsService:
    """Aggregates analytics data from the database into structured summaries."""

    def __init__(self) -> None:
        self._guilds = GuildRepository()
        self._users = UserRepository()
        self._channels = ChannelRepository()

    # ── Period helpers ─────────────────────────────────────────────────────────

    async def period(self, guild_id: int, days: int) -> tuple[date, date]:
        """
        Return ``(start, end)`` for a rolling *days*-day window in guild's timezone.
        """
        settings = await self._guilds.get_settings(guild_id)
        return date_range(settings.timezone, days)

    # ── Guild summary ──────────────────────────────────────────────────────────

    async def summary(
        self,
        guild_id: int,
        start: date,
        end: date,
        user_id: int | None = None,
    ) -> dict:
        """
        Return an analytics summary dict for a guild (or a single user).

        Keys
        ────
        ``messages``      — total messages in period
        ``active_users``  — distinct users with ≥1 message
        ``new_members``   — members who joined
        ``left_members``  — members who left
        ``top_channel``   — name of the most active channel, or None
        ``peak_hour``     — busiest hour (0-23), or None

        When *user_id* is given, ``messages`` is that user's count and
        ``active_users`` / ``new_members`` / ``left_members`` are omitted.
        """
        gid = str(guild_id)

        async with get_session() as session:
            # Guild-level totals
            guild_stmt = select(
                func.coalesce(func.sum(DailyGuildStat.messages), 0),
                func.coalesce(func.sum(DailyGuildStat.new_members), 0),
                func.coalesce(func.sum(DailyGuildStat.left_members), 0),
            ).where(
                DailyGuildStat.guild_id == gid,
                DailyGuildStat.date.between(start, end),
            )
            messages, joined, left = (await session.execute(guild_stmt)).one()

            # Peak hour
            hour_stmt = (
                select(
                    HourlyGuildStat.hour,
                    func.sum(HourlyGuildStat.messages).label("count"),
                )
                .where(
                    HourlyGuildStat.guild_id == gid,
                    HourlyGuildStat.date.between(start, end),
                )
                .group_by(HourlyGuildStat.hour)
                .order_by(text("count DESC"), HourlyGuildStat.hour)
                .limit(1)
            )
            peak = (await session.execute(hour_stmt)).first()

        active_users = await self._users.active_count(guild_id, start, end)
        top_channel = await self._channels.top_channel(guild_id, start, end)

        result: dict = {
            "messages": int(messages),
            "active_users": int(active_users),
            "new_members": int(joined),
            "left_members": int(left),
            "top_channel": top_channel,
            "peak_hour": peak[0] if peak else None,
        }

        if user_id is not None:
            result["messages"] = await self._users.total_messages(
                guild_id, user_id, start, end
            )

        return result

    async def leaderboard(
        self, guild_id: int, start: date, end: date, limit: int = 10
    ) -> list[tuple[str, int]]:
        """Return the top *limit* contributors as ``[(display_name, count)]``."""
        return await self._users.leaderboard(guild_id, start, end, limit)

    # ── Settings accessor ──────────────────────────────────────────────────────

    async def guild_settings_for_reports(self):  # type: ignore[return]
        """Return all GuildSettings rows that have a stats channel configured."""
        return await self._guilds.all_with_channel()

    async def get_settings(self, guild_id: int):  # type: ignore[return]
        """Return GuildSettings for a single guild. Auto-registers guild if not found."""
        try:
            return await self._guilds.get_settings(guild_id)
        except LookupError:
            await self.ensure_guild(guild_id, f"Guild {guild_id}")
            return await self._guilds.get_settings(guild_id)

    async def update_settings(self, guild_id: int, **values: object) -> None:
        """Update GuildSettings fields. Auto-registers guild if not found."""
        try:
            await self._guilds.update_settings(guild_id, **values)
        except LookupError:
            await self.ensure_guild(guild_id, f"Guild {guild_id}")
            await self._guilds.update_settings(guild_id, **values)

    async def ensure_guild(self, guild_id: int, name: str, member_count: int = 0) -> None:
        """Ensure guild is registered. Delegates to GuildRepository."""
        await self._guilds.upsert(guild_id, name, member_count)
