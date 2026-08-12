"""
utils/permissions.py
────────────────────
Discord permission helpers used by slash-command checks.

Usage::

    from utils.permissions import admin_check

    @app_commands.check(admin_check)
    async def my_admin_command(interaction: discord.Interaction) -> None:
        ...
"""

from __future__ import annotations

import discord


def admin_check(interaction: discord.Interaction) -> bool:
    """
    Return True if the invoking user has **Administrator** or **Manage Guild**
    permission in the current guild.

    Also returns False for DM interactions (no guild context).
    """
    if not isinstance(interaction.user, discord.Member):
        return False
    perms = interaction.user.guild_permissions
    return perms.administrator or perms.manage_guild


def can_manage_channels(interaction: discord.Interaction) -> bool:
    """Return True if the user has the Manage Channels permission."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_channels
