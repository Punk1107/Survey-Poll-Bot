"""
reports/weekly_report.py
─────────────────────────
Data class that defines the content of a Weekly Report.

Extends the daily fields with 7-day trend data and week-over-week comparisons.

Fields (in addition to DailyReport fields)
──────────────────────────────────────────
start_date         — First day of the 7-day window
daily_messages     — List of 7 daily message counts (oldest → newest)
prev_messages      — Total messages in the *prior* 7-day window (for WoW %)
most_active_day    — Date with the highest message count in this week
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class WeeklyReport:
    """Structured data for a weekly analytics report."""

    # Period
    start_date: date
    end_date: date

    # Current-week totals (same as DailyReport but 7-day window)
    messages: int
    active_users: int
    new_members: int
    left_members: int
    top_channel: str | None = None
    peak_hour: int | None = None

    # Weekly-specific fields
    daily_messages: list[int] = field(default_factory=list)   # 7 values, Mon→Sun
    prev_messages: int = 0                                      # prior 7-day total
    most_active_day: date | None = None
    leaderboard: list[tuple[str, int]] = field(default_factory=list)

    @property
    def wow_change(self) -> float:
        """Week-over-week fractional change.  Returns 0.0 if no prior data."""
        if self.prev_messages == 0:
            return 0.0
        return (self.messages - self.prev_messages) / self.prev_messages

    @classmethod
    def from_summary(
        cls,
        summary: dict,
        start_date: date,
        end_date: date,
        prev_messages: int = 0,
        daily_messages: list[int] | None = None,
        most_active_day: date | None = None,
        leaderboard: list[tuple[str, int]] | None = None,
    ) -> "WeeklyReport":
        """
        Build a ``WeeklyReport`` from the dict returned by ``AnalyticsService.summary()``.
        """
        return cls(
            start_date=start_date,
            end_date=end_date,
            messages=summary.get("messages", 0),
            active_users=summary.get("active_users", 0),
            new_members=summary.get("new_members", 0),
            left_members=summary.get("left_members", 0),
            top_channel=summary.get("top_channel"),
            peak_hour=summary.get("peak_hour"),
            prev_messages=prev_messages,
            daily_messages=daily_messages or [],
            most_active_day=most_active_day,
            leaderboard=leaderboard or [],
        )
