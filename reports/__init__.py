"""
reports/__init__.py
Re-exports the public surface of the reports package.
"""

from .embeds import build_daily_embed, build_weekly_embed, build_summary_embed
from .formatters import fmt_number, fmt_percent, fmt_peak_hour, bar_chart

__all__ = [
    "build_daily_embed",
    "build_weekly_embed",
    "build_summary_embed",
    "fmt_number",
    "fmt_percent",
    "fmt_peak_hour",
    "bar_chart",
]
