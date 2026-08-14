"""
database/survey_helpers.py
───────────────────────────
Domain helper functions for the Survey system (upserting answers, fetching next question, counting responses).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


async def upsert_answer(
    session: AsyncSession,
    survey_id: int,
    question_id: int,
    user_id: str,
    answer_value: str,
) -> tuple[str, bool]:
    """
    Insert or update a single answer for a user on a survey question.
    Returns (answer_value, is_update).
    """
    from models import Response, Answer

    result = await session.execute(
        select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
    )
    resp_id = result.scalar()

    if not resp_id:
        response = Response(survey_id=survey_id, user_id=user_id)
        try:
            async with session.begin_nested():
                session.add(response)
                await session.flush()
                resp_id = response.id
        except Exception:
            # begin_nested() automatically rolls back only the savepoint on exception.
            result = await session.execute(
                select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
            )
            resp_id = result.scalar()
            if not resp_id:
                raise RuntimeError(
                    f"Could not obtain Response row for survey={survey_id} user={user_id}"
                )

    result = await session.execute(
        select(Answer).filter_by(response_id=resp_id, question_id=question_id)
    )
    existing = result.scalars().first()

    if existing:
        existing.answer = str(answer_value)
        is_update = True
    else:
        session.add(
            Answer(response_id=resp_id, question_id=question_id, answer=str(answer_value))
        )
        is_update = False

    return answer_value, is_update


async def get_next_question(session: AsyncSession, survey_id: int, user_id: str):
    """
    Return the next unanswered Question for a user in a survey.
    """
    from models import Question, Answer, Response

    stmt = (
        select(Question)
        .outerjoin(
            Answer,
            (Answer.question_id == Question.id)
            & (
                Answer.response_id
                == select(Response.id)
                .filter_by(survey_id=survey_id, user_id=user_id)
                .scalar_subquery()
            ),
        )
        .filter(Question.survey_id == survey_id)
        .filter(Answer.id.is_(None))
        .order_by(Question.order, Question.id)
        .limit(1)
    )

    result = await session.execute(stmt)
    return result.scalars().first()


async def get_question_count(session: AsyncSession, survey_id: int) -> int:
    """Return the total number of questions for a survey."""
    from models import Question

    result = await session.execute(
        select(func.count()).select_from(Question).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0


async def get_response_count(session: AsyncSession, survey_id: int) -> int:
    """Return the number of unique respondents for a survey."""
    from models import Response

    result = await session.execute(
        select(func.count()).select_from(Response).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0
