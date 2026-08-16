"""
reports/embeds.py
──────────────────
Discord Embed builders for analytics reports and command responses.

All functions return a ``discord.Embed`` and are pure (no async, no I/O).
Formatting details are delegated to ``reports.formatters`` — nothing is
hard-coded here except embed structure (title / fields / footer / colour).

Public API
──────────
build_summary_embed(title, stats)      — lightweight summary for /stats commands
build_daily_embed(stats, date)         — full daily scheduled report
build_weekly_embed(stats, start, end)  — full weekly scheduled report with trend
"""

from __future__ import annotations

from datetime import date

import discord

from reports.formatters import (
    fmt_member_delta,
    fmt_number,
    fmt_peak_hour,
    fmt_week_over_week,
)

# ── Colour palette ─────────────────────────────────────────────────────────────
_COLOUR_DAILY = discord.Colour.from_rgb(88, 101, 242)    # Discord blurple
_COLOUR_WEEKLY = discord.Colour.from_rgb(87, 242, 135)   # Mint green
_COLOUR_SUMMARY = discord.Colour.blurple()


# ── Command response embed ─────────────────────────────────────────────────────

def build_summary_embed(title: str, stats: dict) -> discord.Embed:
    """
    Lightweight embed for ``/stats`` and ``/leaderboard`` responses.

    Args:
        title: The embed title (e.g. "Server stats: 2025-01-01 to 2025-01-07").
        stats: Dict from ``AnalyticsService.summary()``.
    """
    embed = discord.Embed(title=title, colour=_COLOUR_SUMMARY)

    embed.add_field(
        name="💬 Messages",
        value=fmt_number(stats.get("messages", 0)),
        inline=True,
    )
    embed.add_field(
        name="👥 Active Users",
        value=fmt_number(stats.get("active_users", 0)),
        inline=True,
    )

    top_channel = stats.get("top_channel")
    embed.add_field(
        name="📢 Top Channel",
        value=f"#{top_channel}" if top_channel else "No activity",
        inline=True,
    )

    peak = stats.get("peak_hour")
    embed.add_field(
        name="⏰ Peak Time",
        value=fmt_peak_hour(peak),
        inline=True,
    )

    joined = stats.get("new_members", 0)
    left = stats.get("left_members", 0)
    embed.add_field(
        name="📈 Members",
        value=fmt_member_delta(joined, left),
        inline=True,
    )

    embed.set_footer(text="Analytics Bot V1.1")
    return embed


# ── Daily scheduled report ─────────────────────────────────────────────────────

def build_daily_embed(stats: dict, report_date: date) -> discord.Embed:
    """
    Full embed for a scheduled daily report.

    Args:
        stats:       Dict from ``AnalyticsService.summary()`` (may include ``leaderboard``).
        report_date: The date the report covers (yesterday).
    """
    embed = discord.Embed(
        title=f"📊 Daily Report — {report_date.strftime('%A, %d %B %Y')}",
        colour=_COLOUR_DAILY,
    )

    embed.add_field(
        name="💬 Messages",
        value=fmt_number(stats.get("messages", 0)),
        inline=True,
    )
    embed.add_field(
        name="👥 Active Users",
        value=fmt_number(stats.get("active_users", 0)),
        inline=True,
    )
    embed.add_field(
        name="⏰ Peak Time",
        value=fmt_peak_hour(stats.get("peak_hour")),
        inline=True,
    )

    top_channel = stats.get("top_channel")
    embed.add_field(
        name="📢 Most Active Channel",
        value=f"#{top_channel}" if top_channel else "No activity",
        inline=True,
    )

    joined = stats.get("new_members", 0)
    left = stats.get("left_members", 0)
    embed.add_field(
        name="🧑‍🤝‍🧑 Members",
        value=fmt_member_delta(joined, left),
        inline=True,
    )

    leaderboard: list[tuple[str, int]] = stats.get("leaderboard", [])
    if leaderboard:
        lines = [
            f"`{i}.` **{name}** — {fmt_number(count)} msgs"
            for i, (name, count) in enumerate(leaderboard[:10], start=1)
        ]
        embed.add_field(
            name="🏆 Top Contributors",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text="Analytics Bot V1.1 • Daily Report")
    embed.timestamp = discord.utils.utcnow()
    return embed


# ── Weekly scheduled report ────────────────────────────────────────────────────

def build_weekly_embed(stats: dict, start: date, end: date) -> discord.Embed:
    """
    Full embed for a scheduled weekly report.

    Args:
        stats: Dict from ``AnalyticsService.summary()`` for the 7-day window
               (may include ``leaderboard`` and ``prev_messages``).
        start: First day of the reporting period.
        end:   Last day of the reporting period.
    """
    embed = discord.Embed(
        title=(
            f"📅 Weekly Report — "
            f"{start.strftime('%d %b')} to {end.strftime('%d %b %Y')}"
        ),
        colour=_COLOUR_WEEKLY,
    )

    messages = stats.get("messages", 0)
    prev = stats.get("prev_messages", 0)

    embed.add_field(
        name="💬 Messages",
        value=fmt_week_over_week(messages, prev),
        inline=False,
    )
    embed.add_field(
        name="👥 Active Users",
        value=fmt_number(stats.get("active_users", 0)),
        inline=True,
    )
    embed.add_field(
        name="⏰ Peak Time",
        value=fmt_peak_hour(stats.get("peak_hour")),
        inline=True,
    )

    top_channel = stats.get("top_channel")
    embed.add_field(
        name="📢 Top Channel",
        value=f"#{top_channel}" if top_channel else "No activity",
        inline=True,
    )

    joined = stats.get("new_members", 0)
    left = stats.get("left_members", 0)
    embed.add_field(
        name="🧑‍🤝‍🧑 Member Changes",
        value=fmt_member_delta(joined, left),
        inline=True,
    )

    leaderboard: list[tuple[str, int]] = stats.get("leaderboard", [])
    if leaderboard:
        lines = [
            f"`{i}.` **{name}** — {fmt_number(count)} msgs"
            for i, (name, count) in enumerate(leaderboard[:10], start=1)
        ]
        embed.add_field(
            name="🏆 Weekly Top Contributors",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text="Analytics Bot V1.1 • Weekly Report")
    embed.timestamp = discord.utils.utcnow()
    return embed
