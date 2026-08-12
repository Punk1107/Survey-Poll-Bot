"""
tests/test_reports.py
──────────────────────
Tests for the reports package.

Covers:
  - DailyReport.from_summary()
  - WeeklyReport.from_summary() and wow_change property
  - embeds.build_daily_embed() returns a discord.Embed
  - embeds.build_weekly_embed() returns a discord.Embed
  - formatters (all pure functions — no I/O)
"""

from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DISCORD_TOKEN", "test_token_placeholder")
os.environ.setdefault("DEFAULT_TIMEZONE", "UTC")


# ── DailyReport ────────────────────────────────────────────────────────────────

def test_daily_report_from_summary():
    from reports.daily_report import DailyReport

    summary = {
        "messages": 42,
        "active_users": 7,
        "new_members": 2,
        "left_members": 1,
        "top_channel": "general",
        "peak_hour": 20,
    }
    report = DailyReport.from_summary(summary, date(2025, 1, 1))
    assert report.messages == 42
    assert report.active_users == 7
    assert report.top_channel == "general"
    assert report.peak_hour == 20


# ── WeeklyReport ───────────────────────────────────────────────────────────────

def test_weekly_report_wow_change_positive():
    from reports.weekly_report import WeeklyReport

    report = WeeklyReport(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 7),
        messages=120,
        active_users=10,
        new_members=5,
        left_members=1,
        prev_messages=100,
    )
    assert abs(report.wow_change - 0.20) < 0.001


def test_weekly_report_wow_change_no_prior_data():
    from reports.weekly_report import WeeklyReport

    report = WeeklyReport(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 7),
        messages=50,
        active_users=5,
        new_members=0,
        left_members=0,
        prev_messages=0,
    )
    assert report.wow_change == 0.0


# ── Embeds ─────────────────────────────────────────────────────────────────────

def test_build_daily_embed_returns_embed():
    """build_daily_embed should return a discord.Embed without raising."""
    import discord
    from reports.embeds import build_daily_embed

    stats = {
        "messages": 10,
        "active_users": 3,
        "new_members": 1,
        "left_members": 0,
        "top_channel": "general",
        "peak_hour": 14,
    }
    embed = build_daily_embed(stats, date(2025, 1, 1))
    assert isinstance(embed, discord.Embed)
    assert "Daily Report" in (embed.title or "")


def test_build_weekly_embed_returns_embed():
    """build_weekly_embed should return a discord.Embed without raising."""
    import discord
    from reports.embeds import build_weekly_embed

    stats = {
        "messages": 70,
        "active_users": 8,
        "new_members": 3,
        "left_members": 1,
        "top_channel": "announcements",
        "peak_hour": 19,
        "prev_messages": 60,
    }
    embed = build_weekly_embed(stats, date(2025, 1, 1), date(2025, 1, 7))
    assert isinstance(embed, discord.Embed)
    assert "Weekly Report" in (embed.title or "")
