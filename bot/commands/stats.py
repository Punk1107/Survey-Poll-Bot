"""
bot/commands/stats.py
──────────────────────
Slash command: ``/stats [period]``

Shows server-wide activity statistics for today or the last 7 days.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.analytics_service import AnalyticsService
from reports.embeds import build_summary_embed


def _period_choices() -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name="Today", value="daily"),
        app_commands.Choice(name="Last 7 days", value="weekly"),
    ]


def register_stats_commands(
    tree: app_commands.CommandTree, analytics: AnalyticsService
) -> None:
    """Register the ``/stats`` command on *tree*."""

    @tree.command(name="stats", description="View server activity statistics")
    @app_commands.describe(period="Time period to show (default: Today)")
    @app_commands.choices(period=_period_choices())
    async def stats(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command is only available inside a server.", ephemeral=True
            )
            return

        days = 7 if period and period.value == "weekly" else 1
        start, end = await analytics.period(interaction.guild.id, days)
        summary = await analytics.summary(interaction.guild.id, start, end)

        title = (
            f"Server Stats — {start.isoformat()}"
            if days == 1
            else f"Server Stats — {start.isoformat()} to {end.isoformat()}"
        )
        await interaction.response.send_message(
            embed=build_summary_embed(title, summary)
        )
