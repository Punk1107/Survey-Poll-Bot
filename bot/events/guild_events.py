"""
bot/events/guild_events.py
───────────────────────────
Registers ``on_guild_join`` and ``on_guild_remove`` Discord event handlers.

Responsibility:
  - ``on_guild_join``   → register the new guild and sync slash commands.
  - ``on_guild_remove`` → remove the guild from analytics.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from services.analytics_service import AnalyticsService

log = logging.getLogger(__name__)


def register_guild_events(bot: commands.Bot, analytics: AnalyticsService) -> None:
    """
    Attach guild join/remove event handlers to *bot*.

    Args:
        bot:      The Discord bot instance.
        analytics: AnalyticsService used to register / de-register guilds.
    """

    @bot.event
    async def on_guild_join(guild: discord.Guild) -> None:
        """
        Called when the bot is added to a new guild.

        1. Register the guild in analytics (creates default settings).
        2. Sync slash commands to the guild so they appear immediately.
        """
        log.info("Bot joined guild: %s (%s)", guild.name, guild.id)
        try:
            await analytics.ensure_guild(
                guild.id, guild.name, guild.member_count or 0
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed to register new guild %s: %s", guild.id, exc)

        try:
            await bot.tree.sync(guild=guild)
            log.info("Slash commands synced to guild %s", guild.id)
        except discord.HTTPException as exc:
            log.warning("Failed to sync commands to guild %s: %s", guild.id, exc)

    @bot.event
    async def on_guild_remove(guild: discord.Guild) -> None:
        """Called when the bot is removed from a guild."""
        log.info("Bot removed from guild: %s (%s)", guild.name, guild.id)
        # Note: analytics data is retained (CASCADE delete NOT triggered here).
        # If you want to purge data on bot removal, call GuildRepository.remove().
