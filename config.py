from dotenv import load_dotenv
import os
import logging

load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///surveys.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Startup validation ──────────────────────────────────────────────────────
if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Add it to your .env file."
    )

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file."
    )
