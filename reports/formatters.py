"""
reports/formatters.py
──────────────────────
Pure formatting helpers for numbers, percentages, times, and bar charts.

All functions are stateless — safe to import anywhere with no side effects.
Keep presentation logic here so report builders stay readable.

Examples
────────
    fmt_number(1234567)     → "1,234,567"
    fmt_percent(0.184)      → "+18.4%"
    fmt_peak_hour(20)       → "20:00–21:00"
    bar_chart(7, 10, 10)    → "███████░░░"
"""

from __future__ import annotations


def fmt_number(value: int | float) -> str:
    """Format an integer with thousands separators: 1234 → '1,234'."""
    return f"{int(value):,}"


def fmt_percent(change: float, decimals: int = 1) -> str:
    """
    Format a ratio as a signed percentage string.

    Args:
        change:   Fractional change, e.g. 0.184 means +18.4%.
        decimals: Number of decimal places (default 1).

    Examples::

        fmt_percent(0.184)   → "+18.4%"
        fmt_percent(-0.05)   → "-5.0%"
        fmt_percent(0.0)     → "0.0%"
    """
    sign = "+" if change > 0 else ""
    return f"{sign}{change * 100:.{decimals}f}%"


def fmt_peak_hour(hour: int | None) -> str:
    """
    Format a 0-23 hour integer as a human-readable time range.

    Example::

        fmt_peak_hour(20)   → "20:00–21:00"
        fmt_peak_hour(None) → "No activity"
    """
    if hour is None:
        return "No activity"
    next_hour = (hour + 1) % 24
    return f"{hour:02d}:00–{next_hour:02d}:00"


def bar_chart(value: int, maximum: int, width: int = 10) -> str:
    """
    Return a Unicode block bar proportional to *value* / *maximum*.

    Args:
        value:   The value to represent.
        maximum: The reference maximum (100 % bar).
        width:   Total bar width in characters (default 10).

    Example::

        bar_chart(7, 10, 10)  → "███████░░░"
        bar_chart(0, 10)      → "░░░░░░░░░░"
    """
    if maximum <= 0:
        return "░" * width
    filled = round(width * min(value, maximum) / maximum)
    return "█" * filled + "░" * (width - filled)


def fmt_member_delta(joined: int, left: int) -> str:
    """
    Format member join/leave counts as a delta string.

    Example::

        fmt_member_delta(5, 2)  → "+5 joined / −2 left"
    """
    return f"+{joined:,} joined / −{left:,} left"


def fmt_week_over_week(current: int, previous: int) -> str:
    """
    Return a week-over-week comparison string.

    Example::

        fmt_week_over_week(120, 100) → "120 (↑ +20.0% vs last week)"
        fmt_week_over_week(80, 100)  → "80 (↓ −20.0% vs last week)"
        fmt_week_over_week(100, 0)   → "100 (no prior data)"
    """
    if previous == 0:
        return f"{current:,} (no prior data)"
    change = (current - previous) / previous
    arrow = "↑" if change >= 0 else "↓"
    sign = "+" if change >= 0 else "−"
    return f"{current:,} ({arrow} {sign}{abs(change * 100):.1f}% vs last week)"
