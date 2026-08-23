"""
bot/events/member_events.py
────────────────────────────
Registers ``on_member_join`` and ``on_member_remove`` Discord event handlers.

Responsibility: receive the raw Discord events and hand off to
``ActivityService``.  No business logic here.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from services.activity_service import ActivityService

log = logging.getLogger(__name__)


def register_member_events(bot: commands.Bot, activity: ActivityService) -> None:
    """
    Attach member join/remove event handlers to *bot*.

    Uses ``bot.add_listener()`` instead of ``@bot.event`` so that these
    listeners are *added* alongside any existing handlers rather than
    *replacing* them — which is critical when called from inside setup_hook.

    Args:
        bot:      The Discord bot instance.
        activity: The ActivityService that will record the events.
    """

    async def on_member_join(member: discord.Member) -> None:
        """Record that a member joined the guild."""
        guild = member.guild
        try:
            await activity.record_member_join(
                guild_id=guild.id,
                guild_name=guild.name,
                member_count=guild.member_count or 0,
            )
            log.debug("Member join recorded: guild=%s user=%s", guild.id, member.id)
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed to record member join: %s", exc)

    async def on_member_remove(member: discord.Member) -> None:
        """Record that a member left the guild."""
        guild = member.guild
        try:
            await activity.record_member_leave(
                guild_id=guild.id,
                guild_name=guild.name,
                member_count=guild.member_count or 0,
            )
            log.debug("Member remove recorded: guild=%s user=%s", guild.id, member.id)
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed to record member remove: %s", exc)

    bot.add_listener(on_member_join, "on_member_join")
    bot.add_listener(on_member_remove, "on_member_remove")
    log.info("✅ on_member_join / on_member_remove listeners registered via add_listener")
