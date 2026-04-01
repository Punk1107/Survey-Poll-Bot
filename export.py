import asyncio
import io
import logging
import os
import tempfile

import pandas as pd
from sqlalchemy import select

from database import get_session
from models import Answer, Question, Response

log = logging.getLogger(__name__)


async def _get_survey_df(survey_id: int) -> pd.DataFrame:
    """
    Load all survey answers with question text into a DataFrame.

    FIX: Changed from INNER JOIN to LEFT OUTER JOIN between Question and Answer
    so questions that nobody has answered yet still appear in the export with
    empty answer cells — users won't silently miss unanswered questions in their
    data. The old INNER JOIN silently dropped them.
    Also added survey_id → question filter at the Question level, not Answer,
    to avoid cross-survey data leaking via join expansion.
    """
    async with get_session() as session:
        result = await session.execute(
            select(
                Response.user_id,
                Question.text.label("question"),
                Question.qtype,
                Answer.answer,
            )
            .select_from(Question)
            .outerjoin(Answer,    Answer.question_id == Question.id)
            .outerjoin(Response,  Response.id        == Answer.response_id)
            .filter(Question.survey_id == survey_id)
            .order_by(Response.user_id, Question.order, Question.id)
        )
        rows = result.all()

    return pd.DataFrame(rows, columns=["user_id", "question", "qtype", "answer"])


def _write_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig for Excel compat


def _write_json(df: pd.DataFrame, path: str) -> None:
    df.to_json(path, orient="records", force_ascii=False, indent=2)


async def export_csv(survey_id: int) -> str:
    """Export survey results to a temporary CSV file. Returns the file path."""
    df = await _get_survey_df(survey_id)
    fd, path = tempfile.mkstemp(suffix=".csv", prefix=f"survey_{survey_id}_")
    os.close(fd)
    try:
        await asyncio.to_thread(_write_csv, df, path)
        log.info("Exported survey %d to CSV: %s (%d rows)", survey_id, path, len(df))
        return path
    except Exception:
        # Clean up temp file before re-raising so we don't leak disk space
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


async def export_json(survey_id: int) -> str:
    """Export survey results to a temporary JSON file. Returns the file path."""
    df = await _get_survey_df(survey_id)
    fd, path = tempfile.mkstemp(suffix=".json", prefix=f"survey_{survey_id}_")
    os.close(fd)
    try:
        await asyncio.to_thread(_write_json, df, path)
        log.info("Exported survey %d to JSON: %s (%d rows)", survey_id, path, len(df))
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
