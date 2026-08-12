"""
web/routes.py
──────────────
aiohttp route handlers for the analytics web server.

Routes
──────
GET /          — Rich HTML status dashboard (human-readable)
GET /health    — JSON health payload (machine-readable)
GET /ping      — Plain-text "pong" (simplest UptimeRobot probe)

Future (not yet implemented — stubs return 501):
GET /api/guild/{guild_id}/stats
GET /api/guild/{guild_id}/weekly
GET /api/user/{guild_id}/{user_id}
"""

from __future__ import annotations

import json
import math
import platform
import sys
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from aiohttp import web

from services.analytics_service import AnalyticsService
from web.health import build_health_payload

if TYPE_CHECKING:
    import discord

# ── Helpers ────────────────────────────────────────────────────────────────────

_START_TIME = datetime.now(timezone.utc)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="refresh" content="30" />
  <title>Analytics Bot — Status</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg:      #0f1117;
      --surface: #1a1d2e;
      --border:  #2a2d3e;
      --accent:  #5865f2;
      --accent2: #57f287;
      --text:    #e0e2f0;
      --muted:   #8b8fa8;
      --radius:  14px;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px 16px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 32px;
      width: 100%;
      max-width: 600px;
      margin-bottom: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }}
    .header {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 28px;
    }}
    .avatar {{
      width: 56px; height: 56px;
      border-radius: 50%;
      background: var(--accent);
      display: flex; align-items: center; justify-content: center;
      font-size: 28px;
      flex-shrink: 0;
    }}
    h1 {{ font-size: 1.5rem; font-weight: 700; }}
    .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-top: 2px; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 12px;
      border-radius: 100px;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .badge-online  {{ background: rgba(87,242,135,0.15); color: var(--accent2); }}
    .badge-offline {{ background: rgba(237,66,69,0.15);   color: #ed4245; }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 16px;
    }}
    .stat {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
    }}
    .stat-label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .stat-value {{ font-size: 1.35rem; font-weight: 700; margin-top: 4px; }}
    .dot {{
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--accent2);
      animation: pulse 2s ease-in-out infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50%       {{ opacity: 0.5; transform: scale(0.85); }}
    }}
    .footer {{ color: var(--muted); font-size: 0.78rem; text-align: center; margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="avatar">📊</div>
      <div>
        <h1>{bot_name}</h1>
        <div class="subtitle">Discord Server Analytics Bot V1.1</div>
      </div>
      <span class="badge {status_class}" style="margin-left:auto">
        <span class="dot"></span>
        {status_text}
      </span>
    </div>
    <div class="grid">
      <div class="stat">
        <div class="stat-label">Latency</div>
        <div class="stat-value">{latency}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Guilds</div>
        <div class="stat-value">{guilds}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Uptime</div>
        <div class="stat-value">{uptime}</div>
      </div>
      <div class="stat">
        <div class="stat-label">Python</div>
        <div class="stat-value">{py_version}</div>
      </div>
    </div>
  </div>
  <div class="footer">Analytics Bot V1.1 · Auto-refreshes every 30 s</div>
</body>
</html>"""


def _fmt_uptime(seconds: float) -> str:
    s = int(seconds)
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    return f"{m}m {s}s"


def _json(payload: dict | list, status: int = 200) -> web.Response:
    response = web.Response(
        content_type="application/json",
        text=json.dumps(payload, separators=(",", ":"), default=str),
        status=status,
    )
    response.enable_compression()
    return response


def _parse_int(value: str, name: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text=json.dumps({"error": f"{name} must be an integer"}))
    if parsed < minimum or parsed > maximum:
        raise web.HTTPBadRequest(text=json.dumps({"error": f"{name} must be between {minimum} and {maximum}"}))
    return parsed


def _parse_period(request: web.Request, *, default_days: int = 7, max_days: int = 90) -> tuple[date, date, int]:
    params = request.rel_url.query
    if "start" in params or "end" in params:
        if "start" not in params or "end" not in params:
            raise web.HTTPBadRequest(text=json.dumps({"error": "start and end must be provided together"}))
        try:
            start = date.fromisoformat(params["start"])
            end = date.fromisoformat(params["end"])
        except ValueError:
            raise web.HTTPBadRequest(text=json.dumps({"error": "start and end must use YYYY-MM-DD"}))
        if start > end:
            raise web.HTTPBadRequest(text=json.dumps({"error": "start must be before or equal to end"}))
        days = (end - start).days + 1
        if days > max_days:
            raise web.HTTPBadRequest(text=json.dumps({"error": f"date range cannot exceed {max_days} days"}))
        return start, end, days

    days = _parse_int(params.get("days", str(default_days)), "days", minimum=1, maximum=max_days)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    return start, end, days


# ── Route handlers ─────────────────────────────────────────────────────────────

def make_routes(bot: "discord.Client") -> web.RouteTableDef:
    """
    Build and return the aiohttp route table.

    Args:
        bot: Discord client instance (injected for live metrics).
    """
    routes = web.RouteTableDef()
    analytics = AnalyticsService()

    @routes.get("/")
    async def index(_request: web.Request) -> web.Response:
        """HTML status dashboard."""
        latency = bot.latency
        latency_ms = (
            f"{latency * 1000:.0f} ms" if not math.isnan(latency) else "—"
        )
        is_ready = not bot.is_closed() and not math.isnan(latency)
        uptime_s = (datetime.now(timezone.utc) - _START_TIME).total_seconds()

        html = _HTML_TEMPLATE.format(
            bot_name=bot.user.name if bot.user else "Analytics Bot",
            status_class="badge-online" if is_ready else "badge-offline",
            status_text="Online" if is_ready else "Offline",
            latency=latency_ms,
            guilds=len(bot.guilds),
            uptime=_fmt_uptime(uptime_s),
            py_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        )
        return web.Response(content_type="text/html", text=html)

    @routes.get("/health")
    async def health(_request: web.Request) -> web.Response:
        """JSON health payload for monitoring tools."""
        payload = build_health_payload(bot)
        return _json(payload, status=200 if payload["status"] == "ok" else 503)

    @routes.get("/ping")
    async def ping(_request: web.Request) -> web.Response:
        """Plain-text probe for UptimeRobot."""
        return web.Response(text="pong")

    # ── Future API stubs ───────────────────────────────────────────────────────

    @routes.get("/api/guild/{guild_id}/stats")
    async def api_guild_stats(request: web.Request) -> web.Response:
        """Guild stats API."""
        guild_id = _parse_int(request.match_info["guild_id"], "guild_id", minimum=1, maximum=10**30)
        start, end, days = _parse_period(request)
        summary = await analytics.summary(guild_id, start, end)
        limit = _parse_int(request.rel_url.query.get("limit", "10"), "limit", minimum=1, maximum=50)
        leaderboard = await analytics.leaderboard(guild_id, start, end, limit)
        return _json(
            {
                "guild_id": str(guild_id),
                "period": {"start": start, "end": end, "days": days},
                "summary": summary,
                "leaderboard": [
                    {"display_name": name, "messages": messages}
                    for name, messages in leaderboard
                ],
            }
        )

    @routes.get("/api/guild/{guild_id}/weekly")
    async def api_guild_weekly(request: web.Request) -> web.Response:
        """Guild weekly report API."""
        guild_id = _parse_int(request.match_info["guild_id"], "guild_id", minimum=1, maximum=10**30)
        start, end, days = _parse_period(request, default_days=7, max_days=31)
        summary = await analytics.summary(guild_id, start, end)
        return _json(
            {
                "guild_id": str(guild_id),
                "period": {"start": start, "end": end, "days": days},
                "summary": summary,
            }
        )

    @routes.get("/api/user/{guild_id}/{user_id}")
    async def api_user_stats(request: web.Request) -> web.Response:
        """User stats API."""
        guild_id = _parse_int(request.match_info["guild_id"], "guild_id", minimum=1, maximum=10**30)
        user_id = _parse_int(request.match_info["user_id"], "user_id", minimum=1, maximum=10**30)
        start, end, days = _parse_period(request)
        summary = await analytics.summary(guild_id, start, end, user_id=user_id)
        return _json(
            {
                "guild_id": str(guild_id),
                "user_id": str(user_id),
                "period": {"start": start, "end": end, "days": days},
                "summary": summary,
            }
        )

    return routes
