"""
webserver.py
────────────
Lightweight aiohttp web-server that keeps the process alive when deployed on
platforms like Render (which require an open HTTP port) and serves a health-
check URL that UptimeRobot / BetterStack / etc. can ping every 5 minutes.

Architecture
────────────
  • Runs inside the same asyncio event loop as the Discord bot → zero threads,
    zero extra processes, minimal memory overhead.
  • Exposes three routes:
      GET /        →  Rich HTML status dashboard (human-readable)
      GET /health  →  JSON payload (machine-readable monitoring)
      GET /ping    →  Plain-text "pong" (simplest UptimeRobot probe)
  • Bot reference is injected at startup so live stats (latency, guilds, …)
    can be reflected in responses without any shared state hacks.

Usage (from bot.py setup_hook)
────────────────────────────────
    from webserver import WebServer
    web = WebServer(bot)
    await web.start()   # idempotent — safe to call multiple times

Environment variables
──────────────────────
  PORT   Port to listen on (Render injects this automatically, default 8080)
  HOST   Bind address (default 0.0.0.0)
"""

from __future__ import annotations

import logging
import math
import os
import platform
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from discord.ext import commands

log = logging.getLogger("survey_bot.webserver")

# ── Static assets ─────────────────────────────────────────────────────────────
_START_TIME = datetime.now(timezone.utc)

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="refresh" content="30" />
  <title>Survey Poll Bot — Status</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg:        #0f1117;
      --surface:   #1a1d2e;
      --border:    #2a2d3e;
      --accent:    #5865f2;
      --accent2:   #57f287;
      --accent3:   #fee75c;
      --text:      #e0e2f0;
      --muted:     #8b8fa8;
      --radius:    14px;
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
    .endpoints {{ margin-top: 20px; }}
    .endpoint {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-top: 8px;
      font-size: 0.85rem;
      font-family: 'Courier New', monospace;
    }}
    .method {{ color: var(--accent); font-weight: 600; }}
    .path {{ color: var(--text); }}
    .desc {{ color: var(--muted); margin-left: auto; font-family: 'Inter', sans-serif; }}
    .footer {{
      color: var(--muted);
      font-size: 0.78rem;
      text-align: center;
      margin-top: 8px;
    }}
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
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="avatar">📊</div>
      <div>
        <h1>{bot_name}</h1>
        <div class="subtitle">Survey &amp; Poll Discord Bot</div>
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

    <div class="endpoints">
      <div class="endpoint">
        <span class="method">GET</span>
        <span class="path">/ping</span>
        <span class="desc">Plain-text health probe</span>
      </div>
      <div class="endpoint">
        <span class="method">GET</span>
        <span class="path">/health</span>
        <span class="desc">JSON status (monitoring)</span>
      </div>
    </div>
  </div>

  <div class="footer">
    Auto-refreshes every 30s &nbsp;·&nbsp; Last update: {now_utc} UTC
  </div>
</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uptime() -> str:
    """Return a human-readable uptime string since module import."""
    delta = datetime.now(timezone.utc) - _START_TIME
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _safe_latency_ms(raw_latency: float) -> str:
    """
    Convert bot.latency (seconds) to a display string.
    FIX: bot.latency is `inf` before the first heartbeat — guard that case.
    """
    if math.isfinite(raw_latency):
        return f"{round(raw_latency * 1000)} ms"
    return "—"


# ── Web server class ──────────────────────────────────────────────────────────

class WebServer:
    """
    Lifecycle-managed aiohttp web server.
    Inject the bot instance so routes can reflect live stats.
    """

    def __init__(self, bot: "commands.Bot | None" = None) -> None:
        self._bot     = bot
        self._app     = web.Application()
        self._runner: web.AppRunner | None = None
        self._site:   web.TCPSite | None   = None
        # FIX: idempotency flag — prevents double-bind if setup_hook fires again
        self._started: bool = False

        # Register routes
        self._app.router.add_get("/",       self._handle_root)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/ping",   self._handle_ping)
        # Catch-all → 404 JSON
        self._app.router.add_route("*", "/{path_info:.*}", self._handle_404)

    # ── Route handlers ────────────────────────────────────────────────────────

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Human-readable HTML status dashboard."""
        bot      = self._bot
        is_ready = bot is not None and not bot.is_closed() and bot.is_ready()

        if is_ready:
            latency    = _safe_latency_ms(bot.latency)
            guilds     = str(len(bot.guilds))
            bot_name   = str(bot.user) if bot.user else "Survey Poll Bot"
            status_cls = "badge-online"
            status_txt = "Online"
        else:
            latency    = "—"
            guilds     = "—"
            bot_name   = "Survey Poll Bot"
            status_cls = "badge-offline"
            status_txt = "Starting…"

        html = _HTML_TEMPLATE.format(
            bot_name     = bot_name,
            status_class = status_cls,
            status_text  = status_txt,
            latency      = latency,
            guilds       = guilds,
            uptime       = _uptime(),
            py_version   = f"{sys.version_info.major}.{sys.version_info.minor}",
            now_utc      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        )
        return web.Response(text=html, content_type="text/html")

    async def _handle_health(self, request: web.Request) -> web.Response:
        """
        JSON health-check endpoint.

        HTTP 200 when bot is connected and ready, 503 otherwise.
        UptimeRobot / BetterStack treat non-2xx as a downtime event.
        """
        bot      = self._bot
        # FIX: also check bot.is_ready() — is_closed() alone isn't enough;
        # the bot can be not-closed but still initialising (latency = inf).
        is_ready = bot is not None and not bot.is_closed() and bot.is_ready()

        payload: dict = {
            "status":    "ok"       if is_ready else "starting",
            "uptime":    _uptime(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python":    platform.python_version(),
        }

        if is_ready:
            # FIX: guard inf latency before exposing it in JSON
            latency_raw = bot.latency
            payload["latency_ms"] = round(latency_raw * 1000) if math.isfinite(latency_raw) else None
            payload["guilds"]     = len(bot.guilds)

        status_code = 200 if is_ready else 503
        return web.json_response(payload, status=status_code)

    async def _handle_ping(self, request: web.Request) -> web.Response:
        """
        Simplest possible probe — always returns HTTP 200 with 'pong'.
        Configure UptimeRobot with keyword 'pong' against this URL.
        """
        return web.Response(text="pong")

    async def _handle_404(self, request: web.Request) -> web.Response:
        return web.json_response(
            {"error": "not_found", "path": request.path},
            status=404,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the web-server.
        FIX: Idempotent — safe to call multiple times (e.g. on bot reconnect).
        """
        if self._started:
            log.debug("WebServer.start() called but server is already running — skipped.")
            return

        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))

        self._runner = web.AppRunner(
            self._app,
            access_log=None,   # suppress aiohttp per-request logs; bot has its own
        )
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()
        self._started = True
        log.info("🌐 Web-server listening on http://%s:%d", host, port)

    async def stop(self) -> None:
        """Gracefully shut down the web-server."""
        if self._runner and self._started:
            await self._runner.cleanup()
            self._started = False
            log.info("🌐 Web-server stopped.")
