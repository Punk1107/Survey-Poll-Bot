import logging
from sqlalchemy import func, select, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

log = logging.getLogger(__name__)


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
    """
    Return rating aggregations: count, mean, min, max.
    Cast to Float for AVG so decimal means (e.g. 3.5) are preserved correctly.
    """
    from models import Answer

    async def _run(s: AsyncSession) -> dict:
        result = await s.execute(
            select(
                func.count(Answer.id),
                func.avg(cast(Answer.answer, Float)),
                func.min(cast(Answer.answer, Float)),
                func.max(cast(Answer.answer, Float)),
            ).filter(Answer.question_id == question_id)
        )
        row = result.first()
        if not row or row[0] == 0:
            return {"count": 0, "mean": 0.0, "min": 0, "max": 0}
        return {
            "count": row[0],
            "mean":  round(float(row[1]), 2) if row[1] is not None else 0.0,
            "min":   int(row[2]) if row[2] is not None else 0,
            "max":   int(row[3]) if row[3] is not None else 0,
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
    """
    Format MCQ stats as an ASCII bar-chart string for embed fields.
    Shows percentage and total vote count alongside bars.
    """
    if not stats:
        return "No answers yet."

    total_votes = sum(stats.values())
    max_count   = max(stats.values(), default=1)
    lines: list[str] = []

    for choice, count in stats.items():
        pct   = round(count / total_votes * 100) if total_votes else 0
        bar   = _ascii_bar(count, max_count)
        lines.append(f"`{bar}` **{pct}%** {choice}")

    lines.append(f"\n📊 Total votes: **{total_votes}**")
    return "\n".join(lines)


def build_rating_field(stats: dict) -> str:
    """
    Format rating stats as a visual string.
    Dynamically uses the actual max from the data, caps star display at 5.
    """
    if stats["count"] == 0:
        return "No answers yet."

    mean      = stats["mean"]
    scale_max = stats["max"] if stats["max"] > 5 else 5  # infer scale
    # Show at most 5 stars visually regardless of scale to keep text compact
    star_count = min(5, round(mean * 5 / scale_max)) if scale_max > 0 else 0
    stars = "⭐" * star_count

    return (
        f"{stars} **{mean}** / {scale_max}\n"
        f"Responses: **{stats['count']}** | "
        f"Min: **{stats['min']}** | Max: **{stats['max']}**"
    )
