"""
database/repositories/user_repository.py
─────────────────────────────────────────
All SQL that touches ``analytics_users`` and ``daily_user_stats``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from models import AnalyticsUser, DailyUserStat


class UserRepository:
    """Read/write operations for users and their per-day message counts."""

    async def upsert_user(
        self,
        guild_id: int,
        user_id: int,
        display_name: str,
        is_bot: bool = False,
    ) -> None:
        """
        Insert a new user or update their display name.

        Uses SQLite ``ON CONFLICT … DO UPDATE`` for an atomic upsert.
        """
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO analytics_users (guild_id, user_id, display_name, is_bot)
                    VALUES (:g, :u, :name, :bot)
                    ON CONFLICT(guild_id, user_id)
                    DO UPDATE SET display_name = excluded.display_name
                    """
                ),
                {
                    "g": str(guild_id),
                    "u": str(user_id),
                    "name": display_name,
                    "bot": bool(is_bot),
                },
            )

    async def increment_messages(
        self, guild_id: int, user_id: int, day: date
    ) -> None:
        """Add 1 to the message count for *user_id* on *day*."""
        async with get_session() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO daily_user_stats (guild_id, user_id, date, messages)
                    VALUES (:g, :u, :d, 1)
                    ON CONFLICT(guild_id, user_id, date)
                    DO UPDATE SET messages = messages + 1
                    """
                ),
                {"g": str(guild_id), "u": str(user_id), "d": day},
            )

    async def total_messages(
        self, guild_id: int, user_id: int, start: date, end: date, session: AsyncSession | None = None
    ) -> int:
        """Return the total messages sent by *user_id* between *start* and *end*."""
        async def _query(s: AsyncSession) -> int:
            count = await s.scalar(
                select(func.coalesce(func.sum(DailyUserStat.messages), 0)).where(
                    DailyUserStat.guild_id == str(guild_id),
                    DailyUserStat.user_id == str(user_id),
                    DailyUserStat.date.between(start, end),
                )
            )
            return int(count or 0)

        if session is not None:
            return await _query(session)
        async with get_session() as s:
            return await _query(s)

    async def active_count(
        self, guild_id: int, start: date, end: date, session: AsyncSession | None = None
    ) -> int:
        """Return the number of distinct users who sent at least one message."""
        async def _query(s: AsyncSession) -> int:
            count = await s.scalar(
                select(func.count(func.distinct(DailyUserStat.user_id))).where(
                    DailyUserStat.guild_id == str(guild_id),
                    DailyUserStat.date.between(start, end),
                    DailyUserStat.messages > 0,
                )
            )
            return int(count or 0)

        if session is not None:
            return await _query(session)
        async with get_session() as s:
            return await _query(s)

    async def leaderboard(
        self, guild_id: int, start: date, end: date, limit: int = 10, session: AsyncSession | None = None
    ) -> list[tuple[str, int]]:
        """
        Return the top *limit* contributors as ``[(display_name, message_count)]``,
        ordered by message count descending.
        """
        async def _query(s: AsyncSession) -> list[tuple[str, int]]:
            stmt = (
                select(
                    AnalyticsUser.display_name,
                    func.sum(DailyUserStat.messages).label("count"),
                )
                .join(
                    AnalyticsUser,
                    (AnalyticsUser.guild_id == DailyUserStat.guild_id)
                    & (AnalyticsUser.user_id == DailyUserStat.user_id),
                )
                .where(
                    DailyUserStat.guild_id == str(guild_id),
                    DailyUserStat.date.between(start, end),
                )
                .group_by(AnalyticsUser.user_id, AnalyticsUser.display_name)
                .order_by(text("count DESC"), AnalyticsUser.display_name)
                .limit(limit)
            )
            rows = (await s.execute(stmt)).all()
            return [(name, int(count)) for name, count in rows]

        if session is not None:
            return await _query(session)
        async with get_session() as s:
            return await _query(s)
