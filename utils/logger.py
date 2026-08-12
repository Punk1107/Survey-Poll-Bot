"""
utils/logger.py
──────────────
Centralised logging configuration for the entire bot.

Call ``setup_logging()`` once at process startup (in bot.py) before any other
module emits log records.  All other modules should simply use::

    import logging
    log = logging.getLogger(__name__)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "bot.log") -> None:
    """
    Configure the root logger with a console handler and a rotating file handler.

    Args:
        level:    A valid Python logging level string (DEBUG, INFO, WARNING, …).
        log_file: Path to the log file.  Set to "" or None to disable file logging.
    """
    _VALID = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    level = level.upper()
    if level not in _VALID:
        level = "INFO"

    numeric_level = getattr(logging, level, logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
        handlers.append(file_handler)

    logging.basicConfig(
        level=numeric_level,
        format=fmt,
        datefmt=date_fmt,
        handlers=handlers,
    )

    # Silence overly-verbose third-party loggers
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("discord.client").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
