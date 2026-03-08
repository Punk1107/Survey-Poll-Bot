import pandas as pd
import asyncio
from sqlalchemy import select
from database import get_session
from models import Answer, Question

async def _get_survey_df(survey_id: int) -> pd.DataFrame:
    """Internal helper to load survey data into a pandas DataFrame."""
    async with get_session() as session:
        result = await session.execute(
            select(
                Answer.question_id,
                Question.qtype,
                Answer.answer
            )
            .join(Question, Question.id == Answer.question_id)
            .filter(Question.survey_id == survey_id)
        )
        rows = result.all()
    return pd.DataFrame(rows, columns=["question_id", "qtype", "answer"])

def _export_csv_sync(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)

def _export_json_sync(df: pd.DataFrame, path: str):
    df.to_json(path, orient="records", force_ascii=False)

async def export_csv(survey_id: int) -> str:
    df = await _get_survey_df(survey_id)
    path = f"survey_{survey_id}.csv"
    await asyncio.to_thread(_export_csv_sync, df, path)
    return path

async def export_json(survey_id: int) -> str:
    df = await _get_survey_df(survey_id)
    path = f"survey_{survey_id}.json"
    await asyncio.to_thread(_export_json_sync, df, path)
    return path
