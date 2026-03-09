from sqlalchemy import func, select, cast, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session


def _ascii_bar(count: int, max_count: int, width: int = 10) -> str:
    """Return a padded ASCII progress bar, e.g. '██████░░░░  12'."""
    if max_count == 0:
        return "░" * width + "   0"
    filled = round(width * count / max_count)
    return "█" * filled + "░" * (width - filled) + f"  {count}"


async def mcq_stats(question_id: int, session: AsyncSession | None = None) -> dict[str, int]:
    """
    Return a dict of choice → frequency count, sorted descending.
    Accepts an optional existing session (avoids opening an extra connection).
    """
    from models import Answer

    async def _run(s: AsyncSession) -> dict[str, int]:
        result = await s.execute(
            select(Answer.answer, func.count(Answer.id).label("cnt"))
            .filter(Answer.question_id == question_id)
            .group_by(Answer.answer)
            .order_by(func.count(Answer.id).desc())
        )
        return dict(result.all())

    if session is not None:
        return await _run(session)

    async with get_session() as s:
        return await _run(s)


async def rating_stats(question_id: int, session: AsyncSession | None = None) -> dict:
    """Return rating aggregations: count, mean, min, max."""
    from models import Answer

    async def _run(s: AsyncSession) -> dict:
        result = await s.execute(
            select(
                func.count(Answer.id),
                func.avg(cast(Answer.answer, Integer)),
                func.min(cast(Answer.answer, Integer)),
                func.max(cast(Answer.answer, Integer)),
            ).filter(Answer.question_id == question_id)
        )
        row = result.first()
        if not row or row[0] == 0:
            return {"count": 0, "mean": 0.0, "min": 0, "max": 0}
        return {
            "count": row[0],
            "mean":  round(float(row[1]), 2) if row[1] is not None else 0.0,
            "min":   row[2] or 0,
            "max":   row[3] or 0,
        }

    if session is not None:
        return await _run(session)

    async with get_session() as s:
        return await _run(s)


async def text_answers(question_id: int, session: AsyncSession | None = None) -> list[str]:
    """Return all text answers for a question, newest first."""
    from models import Answer

    async def _run(s: AsyncSession) -> list[str]:
        result = await s.execute(
            select(Answer.answer)
            .filter(Answer.question_id == question_id)
            .order_by(Answer.id.desc())
        )
        return list(result.scalars().all())

    if session is not None:
        return await _run(session)

    async with get_session() as s:
        return await _run(s)


async def response_count(survey_id: int, session: AsyncSession | None = None) -> int:
    """Return the number of distinct respondents for a survey."""
    from models import Response
    from sqlalchemy import func

    async def _run(s: AsyncSession) -> int:
        result = await s.execute(
            select(func.count()).select_from(Response).filter_by(survey_id=survey_id)
        )
        return result.scalar() or 0

    if session is not None:
        return await _run(session)

    async with get_session() as s:
        return await _run(s)


def build_mcq_field(stats: dict[str, int]) -> str:
    """Format MCQ stats as an ASCII bar-chart string for embed fields."""
    if not stats:
        return "No answers yet."
    max_count = max(stats.values()) if stats else 1
    lines = [f"`{_ascii_bar(v, max_count)}` {k}" for k, v in stats.items()]
    return "\n".join(lines)


def build_rating_field(stats: dict) -> str:
    """Format rating stats as a visual string."""
    if stats["count"] == 0:
        return "No answers yet."
    stars = "⭐" * round(stats["mean"])
    return (
        f"{stars} **{stats['mean']}** / 5\n"
        f"Responses: **{stats['count']}** | "
        f"Min: **{stats['min']}** | Max: **{stats['max']}**"
    )
