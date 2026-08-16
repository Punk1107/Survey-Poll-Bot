"""
database/repositories/report_repository.py
───────────────────────────────────────────
All SQL that touches ``analytics_report_deliveries``.

The delivery dedup table prevents duplicate reports when the scheduler loop
fires multiple times within the same minute, or when the bot restarts mid-day.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.exc import IntegrityError

from database.connection import get_session
from models import ReportDelivery

log = logging.getLogger(__name__)


class ReportRepository:
    """Check and record scheduled report deliveries."""

    async def already_delivered(
        self, guild_id: int, report_type: str, period_end: date
    ) -> bool:
        """
        Return True if a report of *report_type* covering *period_end* was
        already sent to *guild_id*.

        Args:
            guild_id:    The Discord guild ID.
            report_type: ``"daily"`` or ``"weekly"``.
            period_end:  The last date of the reporting period.
        """
        async with get_session() as session:
            existing = await session.get(
                ReportDelivery,
                {
                    "guild_id": str(guild_id),
                    "report_type": report_type,
                    "period_end": period_end,
                },
            )
            return existing is not None

    async def mark_delivered(
        self, guild_id: int, report_type: str, period_end: date
    ) -> None:
        """
        Record that a report was successfully delivered.

        Idempotent — if the row already exists (race condition / retry),
        the IntegrityError is caught and silently ignored.  The row
        already exists, which is the desired end-state.

        IMPORTANT: This must NOT raise on duplicate-key — the caller
        (SchedulerService._process_guild) calls this *before* deliver()
        as a "claim" to prevent double-sends.  If an exception propagates
        here, deliver() is never called and the report is silently skipped.
        """
        try:
            async with get_session() as session:
                session.add(
                    ReportDelivery(
                        guild_id=str(guild_id),
                        report_type=report_type,
                        period_end=period_end,
                    )
                )
                await session.flush()  # force INSERT before commit so IntegrityError surfaces here
            log.debug(
                "Marked %s report delivered: guild=%s period_end=%s",
                report_type,
                guild_id,
                period_end,
            )
        except IntegrityError:
            # Row already exists — another concurrent scheduler tick won the race.
            # This is expected behaviour; suppress the error so the caller can
            # decide whether to still attempt delivery.
            log.debug(
                "Duplicate mark_delivered (race condition ignored): "
                "guild=%s report_type=%s period_end=%s",
                guild_id,
                report_type,
                period_end,
            )
