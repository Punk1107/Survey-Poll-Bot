"""
bot/commands/config.py
───────────────────────
Slash command group: ``/config``

Admin-only commands for configuring per-guild analytics settings.

Commands
────────
/config stats-channel <#channel>   — Set the report destination channel
/config daily <on|off>             — Enable / disable daily reports
/config weekly <on|off>            — Enable / disable weekly reports
/config report-time <HH:MM>        — Set the scheduled report time
/config timezone <IANA>            — Set the guild's local timezone
/config status                     — Show current configuration
"""

from __future__ import annotations

import discord
from discord import app_commands

from services.analytics_service import AnalyticsService
from utils.permissions import admin_check
from utils.time import parse_report_time, validate_timezone


def register_config_commands(
    tree: app_commands.CommandTree, analytics: AnalyticsService
) -> None:
    """Register the ``/config`` command group on *tree*."""

    config_group = app_commands.Group(
        name="config",
        description="Configure server analytics (admin only)",
    )

    # ── /config stats-channel ─────────────────────────────────────────────────

    @config_group.command(
        name="stats-channel",
        description="Set the channel that receives scheduled reports",
    )
    @app_commands.describe(channel="Text channel for analytics reports")
    @app_commands.check(admin_check)
    async def stats_channel(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        await analytics.update_settings(
            interaction.guild_id, stats_channel_id=str(channel.id)
        )
        await interaction.response.send_message(
            f"✅ Analytics reports will be sent to {channel.mention}.",
            ephemeral=True,
        )

    # ── /config daily ─────────────────────────────────────────────────────────

    @config_group.command(
        name="daily",
        description="Enable or disable daily reports",
    )
    @app_commands.describe(enabled="Turn daily reports on or off")
    @app_commands.check(admin_check)
    async def daily(
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        await analytics.update_settings(interaction.guild_id, daily_enabled=enabled)
        state = "enabled ✅" if enabled else "disabled ❌"
        await interaction.response.send_message(
            f"Daily reports {state}.", ephemeral=True
        )

    # ── /config weekly ────────────────────────────────────────────────────────

    @config_group.command(
        name="weekly",
        description="Enable or disable weekly reports (sent every Monday)",
    )
    @app_commands.describe(enabled="Turn weekly reports on or off")
    @app_commands.check(admin_check)
    async def weekly(
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        await analytics.update_settings(interaction.guild_id, weekly_enabled=enabled)
        state = "enabled ✅" if enabled else "disabled ❌"
        await interaction.response.send_message(
            f"Weekly reports {state}.", ephemeral=True
        )

    # ── /config report-time ───────────────────────────────────────────────────

    @config_group.command(
        name="report-time",
        description="Set the time scheduled reports are sent (24-hour HH:MM)",
    )
    @app_commands.describe(time="Time in 24-hour format, e.g. 09:00")
    @app_commands.check(admin_check)
    async def report_time(
        interaction: discord.Interaction,
        time: str,
    ) -> None:
        try:
            value = parse_report_time(time)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await analytics.update_settings(interaction.guild_id, report_time=value)
        await interaction.response.send_message(
            f"✅ Report time set to **{value}**.", ephemeral=True
        )

    # ── /config timezone ──────────────────────────────────────────────────────

    @config_group.command(
        name="timezone",
        description="Set the timezone for reports and daily statistics",
    )
    @app_commands.describe(value="IANA timezone, e.g. Asia/Bangkok")
    @app_commands.check(admin_check)
    async def timezone(
        interaction: discord.Interaction,
        value: str,
    ) -> None:
        try:
            tz = validate_timezone(value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await analytics.update_settings(interaction.guild_id, timezone=tz)
        await interaction.response.send_message(
            f"✅ Timezone set to **{tz}**.", ephemeral=True
        )

    # ── /config status ────────────────────────────────────────────────────────

    @config_group.command(
        name="status",
        description="Show the current analytics configuration",
    )
    @app_commands.check(admin_check)
    async def status(interaction: discord.Interaction) -> None:
        try:
            setting = await analytics.get_settings(interaction.guild_id)
        except LookupError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        channel_str = (
            f"<#{setting.stats_channel_id}>"
            if setting.stats_channel_id
            else "Not configured"
        )
        embed = discord.Embed(
            title="⚙️ Analytics Configuration",
            colour=discord.Colour.blurple(),
        )
        embed.add_field(name="Report Channel", value=channel_str, inline=False)
        embed.add_field(
            name="Daily Reports",
            value="✅ Enabled" if setting.daily_enabled else "❌ Disabled",
            inline=True,
        )
        embed.add_field(
            name="Weekly Reports",
            value="✅ Enabled" if setting.weekly_enabled else "❌ Disabled",
            inline=True,
        )
        embed.add_field(name="Report Time", value=setting.report_time, inline=True)
        embed.add_field(name="Timezone", value=setting.timezone, inline=True)
        embed.set_footer(text="Analytics Bot V1.1")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /config test-report ───────────────────────────────────────────────────

    @config_group.command(
        name="test-report",
        description="Send a test analytics report immediately to the configured channel",
    )
    @app_commands.describe(report_type="Type of report to test (daily or weekly)")
    @app_commands.choices(
        report_type=[
            app_commands.Choice(name="Daily Report", value="daily"),
            app_commands.Choice(name="Weekly Report", value="weekly"),
        ]
    )
    @app_commands.check(admin_check)
    async def test_report(
        interaction: discord.Interaction,
        report_type: app_commands.Choice[str],
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            setting = await analytics.get_settings(interaction.guild_id)
        except LookupError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not setting.stats_channel_id:
            await interaction.followup.send(
                "❌ Report channel is not configured. Use `/config stats-channel` first.",
                ephemeral=True,
            )
            return

        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from services.report_service import ReportService

        now = datetime.now(ZoneInfo(setting.timezone))
        period_end = (now - timedelta(days=1)).date()

        report_svc = ReportService(interaction.client, analytics)
        success = await report_svc.deliver(
            interaction.guild_id,
            int(setting.stats_channel_id),
            report_type.value,
            period_end,
        )

        if success:
            await interaction.followup.send(
                f"✅ **{report_type.name}** sent successfully to <#{setting.stats_channel_id}>!",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"❌ Failed to send **{report_type.name}**. Please check bot permissions in <#{setting.stats_channel_id}>.",
                ephemeral=True,
            )

    tree.add_command(config_group)

