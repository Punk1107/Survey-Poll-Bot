"""
database/repositories/channel_repository.py
────────────────────────────────────────────
All SQL that touches ``analytics_channels`` and ``daily_channel_stats``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, text

from database.connection import get_session
from models import AnalyticsChannel, DailyChannelStat


class ChannelRepository:
    """Read/write operations for channels and their per-day message counts."""

    async def upsert_channel(
        self, guild_id: int, channel_id: int, name: str
    ) -> None:
        """Insert a new channel or update its name."""
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO analytics_channels (guild_id, channel_id, name)
                    VALUES (:g, :c, :name)
                    ON CONFLICT(guild_id, channel_id)
                    DO UPDATE SET name = excluded.name
                    """
                ),
                {"g": str(guild_id), "c": str(channel_id), "name": name},
            )

    async def increment_messages(
        self, guild_id: int, channel_id: int, day: date
    ) -> None:
        """Add 1 to the message count for *channel_id* on *day*."""
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO daily_channel_stats (guild_id, channel_id, date, messages)
                    VALUES (:g, :c, :d, 1)
                    ON CONFLICT(guild_id, channel_id, date)
                    DO UPDATE SET messages = messages + 1
                    """
                ),
                {"g": str(guild_id), "c": str(channel_id), "d": day},
            )

    async def top_channel(
        self, guild_id: int, start: date, end: date
    ) -> str | None:
        """Return the name of the most active channel in the date range, or None."""
        async with get_session() as session:
            stmt = (
                select(AnalyticsChannel.name, func.sum(DailyChannelStat.messages).label("count"))
                .join(
                    AnalyticsChannel,
                    (AnalyticsChannel.guild_id == DailyChannelStat.guild_id)
                    & (AnalyticsChannel.channel_id == DailyChannelStat.channel_id),
                )
                .where(
                    DailyChannelStat.guild_id == str(guild_id),
                    DailyChannelStat.date.between(start, end),
                )
                .group_by(AnalyticsChannel.name)
                .order_by(text("count DESC"))
                .limit(1)
            )
            row = (await session.execute(stmt)).first()
            return row[0] if row else None

    async def total_messages(
        self, guild_id: int, channel_id: int, start: date, end: date
    ) -> int:
        """Return total messages in *channel_id* between *start* and *end*."""
        async with get_session() as session:
            count = await session.scalar(
                select(func.coalesce(func.sum(DailyChannelStat.messages), 0)).where(
                    DailyChannelStat.guild_id == str(guild_id),
                    DailyChannelStat.channel_id == str(channel_id),
                    DailyChannelStat.date.between(start, end),
                )
            )
            return int(count or 0)
