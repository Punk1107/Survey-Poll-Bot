"""
database/repositories/activity_repository.py
──────────────────────────────────────────────
Aggregate write operations that span multiple tables in a single transaction.

This is the "hot path" for every Discord message event — it must be fast.
All writes use SQLite ``ON CONFLICT … DO UPDATE`` (UPSERT) to avoid separate
SELECT + INSERT round-trips.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text

from database.connection import get_session

log = logging.getLogger(__name__)


class ActivityRepository:
    """
    Multi-table write operations for recording Discord activity.

    Every method issues a batch of atomic UPSERTs in a single session/transaction
    so partial writes cannot leave the database in an inconsistent state.
    """

    async def record_message(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        display_name: str,
        channel_name: str,
        day: date,
        hour: int,
    ) -> None:
        """
        Increment message counters across all four stat tables for one message event.

        Tables updated:
          - ``analytics_users``        — upsert display name
          - ``analytics_channels``     — upsert channel name
          - ``daily_guild_stats``      — +1 message
          - ``daily_user_stats``       — +1 message
          - ``daily_channel_stats``    — +1 message
          - ``hourly_guild_stats``     — +1 message
          - ``daily_guild_stats``      — recalculate active_users + peak_hour
        """
        g = str(guild_id)
        u = str(user_id)
        c = str(channel_id)
        params = {
            "g": g, "u": u, "c": c,
            "d": day, "h": hour,
            "name": display_name, "channel": channel_name,
        }

        async with get_session() as session:
            # Upsert user and channel metadata
            await session.execute(text("""
                INSERT INTO analytics_users (guild_id, user_id, display_name, is_bot)
                VALUES (:g, :u, :name, FALSE)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET display_name = excluded.display_name
            """), params)

            await session.execute(text("""
                INSERT INTO analytics_channels (guild_id, channel_id, name)
                VALUES (:g, :c, :channel)
                ON CONFLICT(guild_id, channel_id)
                DO UPDATE SET name = excluded.name
            """), params)

            # Increment per-day counters
            await session.execute(text("""
                INSERT INTO daily_guild_stats (guild_id, date, messages)
                VALUES (:g, :d, 1)
                ON CONFLICT(guild_id, date)
                DO UPDATE SET messages = messages + 1
            """), params)

            await session.execute(text("""
                INSERT INTO daily_user_stats (guild_id, user_id, date, messages)
                VALUES (:g, :u, :d, 1)
                ON CONFLICT(guild_id, user_id, date)
                DO UPDATE SET messages = messages + 1
            """), params)

            await session.execute(text("""
                INSERT INTO daily_channel_stats (guild_id, channel_id, date, messages)
                VALUES (:g, :c, :d, 1)
                ON CONFLICT(guild_id, channel_id, date)
                DO UPDATE SET messages = messages + 1
            """), params)

            await session.execute(text("""
                INSERT INTO hourly_guild_stats (guild_id, date, hour, messages)
                VALUES (:g, :d, :h, 1)
                ON CONFLICT(guild_id, date, hour)
                DO UPDATE SET messages = messages + 1
            """), params)

    async def record_member_join(self, guild_id: int, day: date) -> None:
        """Increment ``new_members`` counter for *guild_id* on *day*."""
        await self._bump_member_field(guild_id, day, "new_members")

    async def record_member_leave(self, guild_id: int, day: date) -> None:
        """Increment ``left_members`` counter for *guild_id* on *day*."""
        await self._bump_member_field(guild_id, day, "left_members")

    async def _bump_member_field(
        self, guild_id: int, day: date, field: str
    ) -> None:
        _ALLOWED_FIELDS = {"new_members", "left_members"}
        if field not in _ALLOWED_FIELDS:
            raise ValueError(f"Invalid field name for member bump: {field!r}")
        async with get_session() as session:
            await session.execute(
                text(
                    f"""
                    INSERT INTO daily_guild_stats (guild_id, date, {field})
                    VALUES (:g, :d, 1)
                    ON CONFLICT(guild_id, date)
                    DO UPDATE SET {field} = {field} + 1
                    """
                ),
                {"g": str(guild_id), "d": day},
            )
