"""
bot/commands/__init__.py
Re-exports the command registration functions.
"""

from .stats import register_stats_commands
from .userstats import register_userstats_commands
from .leaderboard import register_leaderboard_commands
from .config import register_config_commands

__all__ = [
    "register_stats_commands",
    "register_userstats_commands",
    "register_leaderboard_commands",
    "register_config_commands",
]
