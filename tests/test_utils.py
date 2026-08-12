"""
tests/test_utils.py
────────────────────
Tests for the utils package (pure functions — no I/O, no database).
"""

from __future__ import annotations

import pytest


# ── utils.time ─────────────────────────────────────────────────────────────────

def test_validate_timezone_valid():
    from utils.time import validate_timezone
    assert validate_timezone("Asia/Bangkok") == "Asia/Bangkok"
    assert validate_timezone("Europe/London") == "Europe/London"
    assert validate_timezone("UTC") == "UTC"


def test_validate_timezone_invalid():
    from utils.time import validate_timezone
    with pytest.raises(ValueError, match="IANA"):
        validate_timezone("Not/ATimezone")


def test_parse_report_time_valid():
    from utils.time import parse_report_time
    assert parse_report_time("09:00") == "09:00"
    assert parse_report_time("23:59") == "23:59"
    assert parse_report_time("00:00") == "00:00"


def test_parse_report_time_invalid():
    from utils.time import parse_report_time
    with pytest.raises(ValueError):
        parse_report_time("9:00")   # missing leading zero
    with pytest.raises(ValueError):
        parse_report_time("25:00")  # hour out of range
    with pytest.raises(ValueError):
        parse_report_time("noon")


def test_date_range():
    from datetime import date, timedelta
    from utils.time import date_range

    # date_range with days=1 should return (today, today)
    start, end = date_range("UTC", 1)
    assert start == end

    # date_range with days=7 should span 7 days
    start7, end7 = date_range("UTC", 7)
    assert (end7 - start7).days == 6  # inclusive: 6 gaps = 7 days


# ── utils.formatters (via reports.formatters) ─────────────────────────────────

def test_fmt_number():
    from reports.formatters import fmt_number
    assert fmt_number(1234) == "1,234"
    assert fmt_number(1000000) == "1,000,000"
    assert fmt_number(0) == "0"


def test_fmt_percent_positive():
    from reports.formatters import fmt_percent
    assert fmt_percent(0.184) == "+18.4%"


def test_fmt_percent_negative():
    from reports.formatters import fmt_percent
    assert fmt_percent(-0.05) == "-5.0%"


def test_fmt_percent_zero():
    from reports.formatters import fmt_percent
    assert fmt_percent(0.0) == "0.0%"


def test_fmt_peak_hour():
    from reports.formatters import fmt_peak_hour
    assert fmt_peak_hour(20) == "20:00–21:00"
    assert fmt_peak_hour(23) == "23:00–00:00"
    assert fmt_peak_hour(None) == "No activity"


def test_bar_chart():
    from reports.formatters import bar_chart
    assert bar_chart(10, 10, 10) == "██████████"
    assert bar_chart(0, 10, 10) == "░░░░░░░░░░"
    assert len(bar_chart(5, 10, 10)) == 10


# ── utils.validators ───────────────────────────────────────────────────────────

def test_validate_time_format_valid():
    from utils.validators import validate_time_format
    assert validate_time_format("09:00") == "09:00"
    assert validate_time_format("23:59") == "23:59"


def test_validate_time_format_invalid():
    from utils.validators import validate_time_format
    with pytest.raises(ValueError):
        validate_time_format("9:00")
    with pytest.raises(ValueError):
        validate_time_format("noon")
