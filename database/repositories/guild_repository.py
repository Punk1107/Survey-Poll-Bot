"""
database/repositories/guild_repository.py
──────────────────────────────────────────
All SQL that touches ``analytics_guilds`` and ``guild_settings``.

Rule: No business logic here.  The repository only knows how to read and write
rows.  Callers decide *when* and *why*.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from database.connection import get_session
from models import AnalyticsGuild, GuildSettings

log = logging.getLogger(__name__)


class GuildRepository:
    """CRUD operations for guilds and their per-guild settings."""

    # ── Guild ──────────────────────────────────────────────────────────────────

    async def upsert(self, guild_id: int, name: str, member_count: int = 0) -> None:
        """
        Insert a new guild or update its name / member count.

        Also creates a default ``GuildSettings`` row if one does not exist.
        """
        from config import DEFAULT_TIMEZONE

        gid = str(guild_id)
        async with get_session() as session:
            row = await session.get(AnalyticsGuild, gid)
            if row is None:
                session.add(
                    AnalyticsGuild(guild_id=gid, name=name, member_count=member_count)
                )
                session.add(
                    GuildSettings(guild_id=gid, timezone=DEFAULT_TIMEZONE)
                )
                log.info("Registered new guild %s (%s)", guild_id, name)
            else:
                row.name = name
                row.member_count = member_count
                settings_row = await session.get(GuildSettings, gid)
                if settings_row is None:
                    session.add(GuildSettings(guild_id=gid, timezone=DEFAULT_TIMEZONE))

    async def remove(self, guild_id: int) -> None:
        """Delete a guild and all cascade-dependent rows."""
        gid = str(guild_id)
        async with get_session() as session:
            row = await session.get(AnalyticsGuild, gid)
            if row:
                await session.delete(row)
                log.info("Removed guild %s from analytics", guild_id)

    # ── Settings ───────────────────────────────────────────────────────────────

    async def get_settings(self, guild_id: int) -> GuildSettings:
        """
        Return the ``GuildSettings`` for *guild_id*.

        Raises ``LookupError`` if the guild is not registered.
        """
        async with get_session() as session:
            row = await session.get(GuildSettings, str(guild_id))
            if row is None:
                raise LookupError(
                    f"Guild {guild_id} is not registered in analytics. "
                    "Has the bot been added to the server?"
                )
            session.expunge(row)
            return row

    async def update_settings(self, guild_id: int, **values: object) -> None:
        """
        Update one or more ``GuildSettings`` fields.

        Allowed keys: ``stats_channel_id``, ``daily_enabled``, ``weekly_enabled``,
        ``report_time``, ``timezone``.

        Raises ``ValueError`` for unrecognised keys.
        Raises ``LookupError`` if the guild is not registered.
        """
        _ALLOWED = {
            "stats_channel_id",
            "daily_enabled",
            "weekly_enabled",
            "report_time",
            "timezone",
        }
        invalid = set(values) - _ALLOWED
        if invalid:
            raise ValueError(f"Unsupported setting(s): {', '.join(sorted(invalid))}")

        async with get_session() as session:
            row = await session.get(GuildSettings, str(guild_id))
            if row is None:
                raise LookupError(f"Guild {guild_id} is not registered in analytics.")
            for key, value in values.items():
                setattr(row, key, value)

    async def all_with_channel(self) -> list[GuildSettings]:
        """
        Return all ``GuildSettings`` rows that have a ``stats_channel_id`` set.

        Used by the scheduler to find guilds that should receive reports.
        """
        async with get_session() as session:
            rows = (
                await session.execute(
                    select(GuildSettings).where(
                        GuildSettings.stats_channel_id.is_not(None)
                    )
                )
            ).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)
