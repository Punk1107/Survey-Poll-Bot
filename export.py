import asyncio
import hashlib
import io
import logging
import os
import tempfile

import pandas as pd
from sqlalchemy import select

from database import get_session
from models import Answer, Question, Response, Survey

log = logging.getLogger(__name__)


async def _get_survey_df(survey_id: int) -> tuple[pd.DataFrame, bool]:
    """
    Load all survey answers with question text into a DataFrame.
    Returns (df, is_anonymous).

    Uses LEFT OUTER JOIN so questions that nobody has answered yet still appear
    in the export with empty answer cells — the old INNER JOIN silently dropped them.

    FIX: Also returns is_anonymous so the caller can decide whether to mask user IDs.
    """
    async with get_session() as session:
        # Fetch the is_anonymous flag in the same session
        survey = await session.get(Survey, survey_id)
        is_anonymous = bool(survey and survey.is_anonymous)

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

    df = pd.DataFrame(rows, columns=["user_id", "question", "qtype", "answer"])

    # FIX: Privacy — mask user IDs for anonymous surveys using a SHA-256 prefix
    # so the export still lets you count unique respondents without exposing Discord IDs.
    if is_anonymous and not df.empty:
        df["user_id"] = df["user_id"].apply(
            lambda uid: "anon_" + hashlib.sha256(str(uid).encode()).hexdigest()[:12]
            if pd.notna(uid) else uid
        )

    return df, is_anonymous


def _write_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig for Excel compat


def _write_json(df: pd.DataFrame, path: str) -> None:
    df.to_json(path, orient="records", force_ascii=False, indent=2)


async def export_csv(survey_id: int) -> str:
    """Export survey results to a temporary CSV file. Returns the file path."""
    df, is_anonymous = await _get_survey_df(survey_id)
    fd, path = tempfile.mkstemp(suffix=".csv", prefix=f"survey_{survey_id}_")
    os.close(fd)
    try:
        await asyncio.to_thread(_write_csv, df, path)
        log.info(
            "Exported survey %d to CSV: %s (%d rows, anonymous=%s)",
            survey_id, path, len(df), is_anonymous,
        )
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


async def export_json(survey_id: int) -> str:
    """Export survey results to a temporary JSON file. Returns the file path."""
    df, is_anonymous = await _get_survey_df(survey_id)
    fd, path = tempfile.mkstemp(suffix=".json", prefix=f"survey_{survey_id}_")
    os.close(fd)
    try:
        await asyncio.to_thread(_write_json, df, path)
        log.info(
            "Exported survey %d to JSON: %s (%d rows, anonymous=%s)",
            survey_id, path, len(df), is_anonymous,
        )
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
