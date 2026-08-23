"""
bot/events/message_events.py
──────────────────────────────
Registers the ``on_message`` Discord event handler.

Responsibility: receive the raw Discord event, validate it, and hand off to
``ActivityService``.  No business logic here — only event routing.

What is NOT done here:
  - SQL queries
  - Statistics aggregation
  - Embed building
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from services.activity_service import ActivityService

log = logging.getLogger(__name__)


def register_message_events(bot: commands.Bot, activity: ActivityService) -> None:
    """
    Attach the ``on_message`` event handler to *bot*.

    Uses ``bot.add_listener()`` instead of ``@bot.event`` so that this
    listener is *added* alongside any existing handlers rather than
    *replacing* them — which is critical when called from inside setup_hook.

    Args:
        bot:      The Discord bot instance.
        activity: The ActivityService that will record the event.
    """

    async def on_message(message: discord.Message) -> None:
        """
        Record aggregate message activity.

        Filters:
          - Ignores bot messages (including the bot itself).
          - Ignores DMs (no guild context).
          - Message *content* is never read or stored — only metadata
            (guild, channel, user) is forwarded to ActivityService.
        """
        # Let discord.py process built-in prefix commands (e.g. surveys)
        await bot.process_commands(message)

        # Filter: ignore bots and DMs
        if message.author.bot:
            return
        if message.guild is None:
            return

        guild = message.guild
        channel = message.channel

        # Channel must be a text channel to have a meaningful name
        channel_name = getattr(channel, "name", str(channel.id))

        log.info(
            "📨 MESSAGE | guild=%s (%s) | channel=%s (#%s) | user=%s (%s)",
            guild.id,
            guild.name,
            channel.id,
            channel_name,
            message.author.id,
            message.author.display_name,
        )

        try:
            await activity.record_message(
                guild_id=guild.id,
                guild_name=guild.name,
                member_count=guild.member_count or 0,
                channel_id=channel.id,
                channel_name=channel_name,
                user_id=message.author.id,
                display_name=message.author.display_name,
            )
            log.info(
                "✅ RECORDED | guild=%s | channel=%s | user=%s",
                guild.id,
                channel.id,
                message.author.id,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "❌ FAILED to record message | guild=%s | channel=%s | user=%s | error=%s",
                guild.id,
                channel.id,
                message.author.id,
                exc,
            )

    bot.add_listener(on_message, "on_message")
    log.info("✅ on_message listener registered via add_listener")
