"""
reports/daily_report.py
────────────────────────
Data class that defines the content of a Daily Report.

The ``DailyReport`` dataclass is populated by ``ReportService`` from the
analytics summary dict, then passed to ``embeds.build_daily_embed()`` for
rendering.  Keeping data separate from presentation makes both easier to test.

Fields
──────
date          — The date the report covers (yesterday's date)
messages      — Total messages sent
active_users  — Distinct users who sent ≥1 message
new_members   — Members who joined
left_members  — Members who left
top_channel   — Name of the most active channel (or None)
peak_hour     — Busiest hour 0-23 (or None)
leaderboard   — List of (display_name, message_count) tuples, top-10
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class DailyReport:
    """Structured data for a daily analytics report."""

    date: date
    messages: int
    active_users: int
    new_members: int
    left_members: int
    top_channel: str | None = None
    peak_hour: int | None = None
    leaderboard: list[tuple[str, int]] = field(default_factory=list)

    @classmethod
    def from_summary(
        cls,
        summary: dict,
        report_date: date,
        leaderboard: list[tuple[str, int]] | None = None,
    ) -> "DailyReport":
        """
        Build a ``DailyReport`` from the dict returned by ``AnalyticsService.summary()``.
        """
        return cls(
            date=report_date,
            messages=summary.get("messages", 0),
            active_users=summary.get("active_users", 0),
            new_members=summary.get("new_members", 0),
            left_members=summary.get("left_members", 0),
            top_channel=summary.get("top_channel"),
            peak_hour=summary.get("peak_hour"),
            leaderboard=leaderboard or [],
        )
