from dotenv import load_dotenv
import os
import logging

load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///surveys.db")
_raw_log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Startup validation ──────────────────────────────────────────────────────
if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Add it to your .env file."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file."
    )

# FIX: Validate LOG_LEVEL. Previously getattr() silently returned None for
# invalid values (e.g. "VERBOSE"), and basicConfig would then silently ignore
# it — potentially setting level=0 (NOTSET) which logs absolutely everything.
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
if _raw_log_level not in _VALID_LOG_LEVELS:
    import warnings
    warnings.warn(
        f"LOG_LEVEL '{_raw_log_level}' is not a valid Python logging level. "
        f"Valid options: {', '.join(sorted(_VALID_LOG_LEVELS))}. Defaulting to INFO.",
        stacklevel=2,
    )
    _raw_log_level = "INFO"

LOG_LEVEL: str = _raw_log_level
