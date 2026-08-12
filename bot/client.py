"""
bot/client.py
──────────────
Creates and configures the Discord bot instance.

Responsibilities:
  • Set up ``discord.Intents`` (message_content, members).
  • Instantiate ``commands.Bot`` with the slash-command tree.
  • Provide ``create_bot()`` as the single factory used by ``bot.py``.

The actual event registration and cog loading happens in ``bot.py``'s
``setup_hook`` to keep this module focused on construction only.
"""

from __future__ import annotations

import discord
from discord.ext import commands


def create_bot() -> commands.Bot:
    """
    Create and return a configured ``commands.Bot`` instance.

    Intents
    -------
    - ``default``         — presence, guilds, guild_messages, reactions, …
    - ``message_content`` — required to read message text (for analytics counting)
    - ``members``         — required for on_member_join / on_member_remove events

    Returns:
        A fully-configured ``commands.Bot`` ready to have events registered.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = commands.Bot(
        command_prefix="!",   # prefix commands unused but required by the class
        intents=intents,
        help_command=None,    # disable the default !help command
    )

    return bot
