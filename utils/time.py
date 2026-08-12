"""
utils/time.py
─────────────
Timezone and date-range helpers used throughout the bot.

All public functions are pure — no I/O, no database access — so they are
trivially testable and safe to import anywhere.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_timezone(value: str) -> str:
    """
    Validate that *value* is a recognised IANA timezone name.

    Returns the value unchanged on success.
    Raises ``ValueError`` with a human-readable message on failure.
    """
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError(
            f"'{value}' is not a valid IANA timezone. "
            "Example: Asia/Bangkok, Europe/London, America/New_York."
        ) from exc
    return value


def parse_report_time(value: str) -> str:
    """
    Validate and normalise a 24-hour ``HH:MM`` time string.

    Returns the canonical ``HH:MM`` form on success.
    Raises ``ValueError`` on failure.
    """
    import re
    if not re.match(r"^\d{2}:\d{2}$", value):
        raise ValueError(f"'{value}' must be in 24-hour HH:MM format, e.g. 09:00.")
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError(
            f"'{value}' is not a valid time. Use 24-hour HH:MM format, e.g. 09:00."
        ) from exc
    return parsed.strftime("%H:%M")


# ── Date-range helpers ─────────────────────────────────────────────────────────

def now_in(timezone: str) -> datetime:
    """Return the current datetime in the given IANA timezone."""
    return datetime.now(ZoneInfo(timezone))


def today_in(timezone: str) -> date:
    """Return today's local date in the given IANA timezone."""
    return now_in(timezone).date()


def daily_boundary(timezone: str) -> tuple[date, date]:
    """
    Return ``(start, end)`` for the current calendar day in *timezone*.

    Both start and end are the same date (today).
    """
    today = today_in(timezone)
    return today, today


def weekly_boundary(timezone: str) -> tuple[date, date]:
    """
    Return ``(start, end)`` for the rolling 7-day window ending today.

    ``start`` = today − 6 days, ``end`` = today.
    """
    today = today_in(timezone)
    return today - timedelta(days=6), today


def date_range(timezone: str, days: int) -> tuple[date, date]:
    """
    Return ``(start, end)`` for a rolling *days*-day window ending today.

    Args:
        timezone: IANA timezone string.
        days:     Number of days in the window (1 = today only, 7 = last week, …).
    """
    end = today_in(timezone)
    start = end - timedelta(days=days - 1)
    return start, end
