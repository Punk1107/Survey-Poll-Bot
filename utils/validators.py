"""
utils/validators.py
────────────────────
Input validation helpers for slash-command arguments.

All functions raise ``ValueError`` on invalid input so callers can catch a
single exception type and forward the message to the Discord user.
"""

from __future__ import annotations

import re

import discord


# ── Discord entity validators ──────────────────────────────────────────────────

def validate_channel(channel: discord.abc.GuildChannel | None) -> discord.TextChannel:
    """
    Ensure *channel* is a non-None ``TextChannel``.

    Raises ``ValueError`` if the check fails.
    """
    if channel is None:
        raise ValueError("No channel provided.")
    if not isinstance(channel, discord.TextChannel):
        raise ValueError(f"#{channel.name} is not a text channel.")
    return channel


def validate_guild_context(interaction: discord.Interaction) -> None:
    """
    Raise ``ValueError`` if the interaction was not sent inside a guild.
    """
    if interaction.guild is None:
        raise ValueError("This command is only available inside a server.")


# ── String validators ──────────────────────────────────────────────────────────

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def validate_time_format(value: str) -> str:
    """
    Validate that *value* looks like a HH:MM string.

    Does *not* check whether the time is semantically valid (use
    ``utils.time.parse_report_time`` for full validation).
    """
    if not _TIME_RE.match(value):
        raise ValueError(f"'{value}' must be in HH:MM format (24-hour clock).")
    return value
