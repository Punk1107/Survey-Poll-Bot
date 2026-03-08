from sqlalchemy import func, select, cast, Integer
from database import get_session
from models import Answer

async def mcq_stats(question_id: int) -> dict[str, int]:
    """
    Returns a dictionary of choice answers mapped to their frequency counts.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Answer.answer, func.count(Answer.id))
            .filter(Answer.question_id == question_id)
            .group_by(Answer.answer)
        )
        return dict(result.all())

async def rating_stats(question_id: int) -> dict:
    """
    Returns rating aggregations: count, mean, min, max.
    """
    async with get_session() as session:
        result = await session.execute(
            select(
                func.count(Answer.id),
                func.avg(cast(Answer.answer, Integer)),
                func.min(cast(Answer.answer, Integer)),
                func.max(cast(Answer.answer, Integer))
            )
            .filter(Answer.question_id == question_id)
        )
        row = result.first()
        
        if not row or row[0] == 0:
            return {"count": 0, "mean": 0, "min": 0, "max": 0}
        
        return {
            "count": row[0],
            "mean": round(float(row[1]), 2) if row[1] is not None else 0,
            "min": row[2] or 0,
            "max": row[3] or 0,
        }

async def text_answers(question_id: int) -> list[str]:
    """
    Returns a list of all text answers.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Answer.answer)
            .filter(Answer.question_id == question_id)
            .order_by(Answer.id.desc())
        )
        return result.scalars().all()
