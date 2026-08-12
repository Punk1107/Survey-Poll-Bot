"""
bot/commands/userstats.py
──────────────────────────
Slash command: ``/userstats [user] [period]``

Shows activity statistics for a specific member.  Defaults to the invoking user.
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


def register_userstats_commands(
    tree: app_commands.CommandTree, analytics: AnalyticsService
) -> None:
    """Register the ``/userstats`` command on *tree*."""

    @tree.command(
        name="userstats",
        description="View a member's activity statistics",
    )
    @app_commands.describe(
        user="Member to inspect (defaults to you)",
        period="Time period to show (default: Today)",
    )
    @app_commands.choices(period=_period_choices())
    async def userstats(
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        period: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command is only available inside a server.", ephemeral=True
            )
            return

        target = user or interaction.user
        days = 7 if period and period.value == "weekly" else 1
        start, end = await analytics.period(interaction.guild.id, days)
        summary = await analytics.summary(
            interaction.guild.id, start, end, user_id=target.id
        )

        period_label = (
            start.isoformat()
            if days == 1
            else f"{start.isoformat()} to {end.isoformat()}"
        )

        embed = discord.Embed(
            title=f"Activity — {target.display_name}",
            description=(
                f"**{summary['messages']:,}** messages "
                f"({period_label})"
            ),
            colour=discord.Colour.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Analytics Bot V1.1")

        await interaction.response.send_message(embed=embed)
