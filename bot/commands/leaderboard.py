"""
bot/commands/leaderboard.py
────────────────────────────
Slash command: ``/leaderboard [period]``

Shows the top contributors (by message count) for today or the last 7 days.
"""

from __future__ import annotations

import discord
from discord import app_commands

from services.analytics_service import AnalyticsService


def _period_choices() -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name="Today", value="daily"),
        app_commands.Choice(name="Last 7 days", value="weekly"),
    ]


def register_leaderboard_commands(
    tree: app_commands.CommandTree, analytics: AnalyticsService
) -> None:
    """Register the ``/leaderboard`` command on *tree*."""

    @tree.command(
        name="leaderboard",
        description="Show the most active members",
    )
    @app_commands.describe(period="Time period to rank (default: Last 7 days)")
    @app_commands.choices(period=_period_choices())
    async def leaderboard(
        interaction: discord.Interaction,
        period: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command is only available inside a server.", ephemeral=True
            )
            return

        # Default to weekly for leaderboard — more interesting than just today
        days = 1 if period and period.value == "daily" else 7
        start, end = await analytics.period(interaction.guild.id, days)
        entries = await analytics.leaderboard(interaction.guild.id, start, end)

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        if entries:
            lines = [
                f"{medals.get(i, f'**{i}.**')} {name} — {count:,} msgs"
                for i, (name, count) in enumerate(entries, 1)
            ]
            description = "\n".join(lines)
        else:
            description = "No activity recorded for this period."

        period_label = (
            end.isoformat()
            if days == 1
            else f"{start.isoformat()} to {end.isoformat()}"
        )

        embed = discord.Embed(
            title="🏆 Top Contributors",
            description=description[:4000],
            colour=discord.Colour.gold(),
        )
        embed.set_footer(text=f"Analytics Bot V1.1 • {period_label}")

        await interaction.response.send_message(embed=embed)
