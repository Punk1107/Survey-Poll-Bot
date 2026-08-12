"""
web/health.py
──────────────
Health check JSON response builder.

Used by:
  - ``GET /health`` — machine-readable status for monitoring tools
  - Render.com / UptimeRobot / BetterStack probes
"""

from __future__ import annotations

import math
import platform
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

_START_TIME = datetime.now(timezone.utc)


def build_health_payload(bot: "discord.Client") -> dict:
    """
    Return a dict of current bot health metrics.

    Args:
        bot: The Discord client (used to read latency, guild count).

    Returns:
        A JSON-serialisable dict with the following keys:
        - ``status``     — "ok" or "degraded"
        - ``latency_ms`` — WebSocket latency in milliseconds (or null)
        - ``guilds``     — number of guilds the bot is in
        - ``uptime_s``   — process uptime in seconds
        - ``python``     — Python version string
        - ``platform``   — OS platform string
        - ``timestamp``  — ISO 8601 UTC timestamp
    """
    now = datetime.now(timezone.utc)
    uptime_s = (now - _START_TIME).total_seconds()

    latency = bot.latency  # seconds; nan if not connected
    latency_ms = (
        round(latency * 1000, 1)
        if not math.isnan(latency)
        else None
    )

    is_ready = not bot.is_closed() and latency_ms is not None
    status = "ok" if is_ready else "degraded"

    return {
        "status": status,
        "latency_ms": latency_ms,
        "guilds": len(bot.guilds),
        "uptime_s": round(uptime_s, 1),
        "python": sys.version,
        "platform": platform.platform(),
        "timestamp": now.isoformat(),
    }
