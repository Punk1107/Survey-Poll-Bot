"""
services/activity_service.py
──────────────────────────────
Thin orchestration layer between Discord events and the repository layer.

Flow::

    Discord event (on_message / on_member_join / on_member_remove)
        ↓
    ActivityService          ← here (orchestration)
        ↓
    GuildRepository          ← ensure guild exists
    ActivityRepository       ← UPSERT counters

Business rule: bots are ignored (message.author.bot == True is filtered in the
event handler before reaching this service).
"""

from __future__ import annotations

import logging
from datetime import datetime
from time import monotonic

from zoneinfo import ZoneInfo

from database.repositories import ActivityRepository, GuildRepository
from utils.time import today_in

log = logging.getLogger(__name__)


class ActivityService:
    """Orchestrates activity recording across guild, user, and channel tables."""

    _GUILD_CACHE_TTL_S = 300
    _SETTINGS_CACHE_TTL_S = 60

    def __init__(self) -> None:
        self._guilds = GuildRepository()
        self._activity = ActivityRepository()
        self._guild_cache: dict[int, tuple[float, str, int]] = {}
        self._timezone_cache: dict[int, tuple[float, ZoneInfo]] = {}

    async def _ensure_guild_cached(
        self, guild_id: int, guild_name: str, member_count: int
    ) -> None:
        now = monotonic()
        cached = self._guild_cache.get(guild_id)
        if (
            cached is not None
            and now - cached[0] < self._GUILD_CACHE_TTL_S
            and cached[1] == guild_name
            and cached[2] == member_count
        ):
            return

        await self._guilds.upsert(guild_id, guild_name, member_count)
        self._guild_cache[guild_id] = (now, guild_name, member_count)

    async def _timezone_for_guild(self, guild_id: int) -> ZoneInfo:
        now = monotonic()
        cached = self._timezone_cache.get(guild_id)
        if cached is not None and now - cached[0] < self._SETTINGS_CACHE_TTL_S:
            return cached[1]

        try:
            settings = await self._guilds.get_settings(guild_id)
            tz = ZoneInfo(settings.timezone)
        except LookupError:
            log.warning("Guild %s not found in settings after upsert - using UTC", guild_id)
            tz = ZoneInfo("UTC")

        self._timezone_cache[guild_id] = (now, tz)
        return tz

    async def record_message(
        self,
        *,
        guild_id: int,
        guild_name: str,
        member_count: int,
        channel_id: int,
        channel_name: str,
        user_id: int,
        display_name: str,
        occurred_at: datetime | None = None,
    ) -> None:
        """
        Record one message event.

        Steps:
        1. Ensure the guild is registered (upsert).
        2. Resolve the local date and hour from guild timezone.
        3. UPSERT all stat counters via ActivityRepository.
        """
        # 1. Ensure guild exists
        await self._ensure_guild_cached(guild_id, guild_name, member_count)

        # 2. Determine local day and hour
        tz = await self._timezone_for_guild(guild_id)

        local = (occurred_at or datetime.now(tz)).astimezone(tz)
        day, hour = local.date(), local.hour

        # 3. Record in all stat tables
        await self._activity.record_message(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            display_name=display_name,
            channel_name=channel_name,
            day=day,
            hour=hour,
        )

    async def record_member_join(
        self, guild_id: int, guild_name: str, member_count: int
    ) -> None:
        """Record a member-join event."""
        await self._ensure_guild_cached(guild_id, guild_name, member_count)
        tz = await self._timezone_for_guild(guild_id)
        day = datetime.now(tz).date()
        await self._activity.record_member_join(guild_id, day)

    async def record_member_leave(
        self, guild_id: int, guild_name: str, member_count: int
    ) -> None:
        """Record a member-leave event."""
        await self._ensure_guild_cached(guild_id, guild_name, member_count)
        tz = await self._timezone_for_guild(guild_id)
        day = datetime.now(tz).date()
        await self._activity.record_member_leave(guild_id, day)
