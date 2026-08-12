"""
database/__init__.py
Re-exports the public surface of the database package.
"""

from .connection import DATABASE_DIALECT, engine, get_session
from .migrations import run_migrations
from .survey_helpers import (
    upsert_answer,
    get_next_question,
    get_question_count,
    get_response_count,
)

__all__ = [
    "engine",
    "DATABASE_DIALECT",
    "get_session",
    "run_migrations",
    "upsert_answer",
    "get_next_question",
    "get_question_count",
    "get_response_count",
]
