"""
web/webserver.py
─────────────────
Lightweight aiohttp web server that keeps the process alive on Render and
provides a health-check endpoint for monitoring tools.

Architecture
────────────
• Runs inside the same asyncio event loop as the Discord bot — zero threads.
• All routes are defined in ``web.routes`` and injected with the bot reference.
• Start / stop are idempotent — safe to call multiple times.

Usage (from bot.py setup_hook / on_close)::

    from web import WebServer

    web = WebServer(bot)
    await web.start()   # in setup_hook
    await web.stop()    # in on_close

Environment variables
─────────────────────
PORT   Port to listen on (Render injects this; default 8080)
HOST   Bind address (default 0.0.0.0)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from aiohttp import web

from web.routes import make_routes

if TYPE_CHECKING:
    import discord

log = logging.getLogger(__name__)


class WebServer:
    """Manages the lifecycle of the aiohttp application."""

    def __init__(self, bot: "discord.Client") -> None:
        self._bot = bot
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Start the HTTP server (idempotent)."""
        if self._runner is not None:
            return  # already running

        app = web.Application()
        app.add_routes(make_routes(self._bot))

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()

        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))

        site = web.TCPSite(self._runner, host, port)
        await site.start()
        log.info("Web server listening on http://%s:%d", host, port)

    async def stop(self) -> None:
        """Gracefully shut down the HTTP server (idempotent)."""
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        log.info("Web server stopped.")
