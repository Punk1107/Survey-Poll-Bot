"""
bot/__init__.py
Re-exports the public surface of the bot package.
"""

from .client import create_bot

__all__ = ["create_bot"]
