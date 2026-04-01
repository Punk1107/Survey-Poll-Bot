import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL

log = logging.getLogger(__name__)

# ── Engine setup ────────────────────────────────────────────────────────────
_is_sqlite = DATABASE_URL.startswith("sqlite")

# Convert bare sqlite:// → sqlite+aiosqlite://
async_db_url = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

_engine_kwargs: dict = {
    "echo": False,
}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(async_db_url, **_engine_kwargs)


# ── Schema migrations ────────────────────────────────────────────────────────
async def run_migrations() -> None:
    """
    Add any columns that exist in the ORM models but are missing from the
    live database (SQLite ALTER TABLE IF NOT EXISTS is not supported, so we
    check PRAGMA table_info and add manually).
    """
    _pending: list[tuple[str, str, str, str]] = [
        ("surveys",   "description",   "TEXT",    "NULL"),
        ("surveys",   "max_responses", "INTEGER", "NULL"),
        ("questions", "order",         "INTEGER", "0"),
    ]

    async with engine.begin() as conn:
        for table, column, col_type, default in _pending:
            rows = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in rows}
            if column not in existing:
                await conn.execute(
                    text(
                        f"ALTER TABLE {table} "
                        f"ADD COLUMN {column} {col_type} DEFAULT {default}"
                    )
                )
                log.info("Migration: added column '%s.%s'", table, column)


# ── SQLite PRAGMAs ──────────────────────────────────────────────────────────
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    """
    Applied once per physical SQLite connection.
    WAL mode → better concurrent read/write throughput.
    foreign_keys=ON → enforce referential integrity at the DB level.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")   # safe + faster than FULL
    cursor.execute("PRAGMA cache_size=-32000")    # 32 MB page cache
    cursor.execute("PRAGMA temp_store=MEMORY")    # keep temp tables in RAM
    cursor.close()


# ── Session factory ─────────────────────────────────────────────────────────
_AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides a scoped AsyncSession.
    Commits on success, rolls back on any exception, always closes.
    """
    session: AsyncSession = _AsyncSessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ── Domain helpers ──────────────────────────────────────────────────────────
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

    Race-condition handling: if two requests try to create the Response row
    simultaneously (unique constraint violation on flush), we catch the
    exception, roll back, then re-fetch the winning row.

    IMPORTANT: After a rollback, the SQLAlchemy async session begins a NEW
    implicit transaction automatically when the next statement runs, so it
    is perfectly safe to continue using the session post-rollback.
    """
    from models import Response, Answer
    from sqlalchemy import select

    # 1. Get or create the Response row for (survey, user)
    result = await session.execute(
        select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
    )
    resp_id = result.scalar()

    if not resp_id:
        response = Response(survey_id=survey_id, user_id=user_id)
        session.add(response)
        try:
            await session.flush()
            resp_id = response.id
        except Exception:
            # UniqueConstraint race: roll back, then re-fetch winning row.
            # The session is still usable after rollback — SQLAlchemy async
            # begins a new implicit transaction on the next statement.
            await session.rollback()
            result = await session.execute(
                select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
            )
            resp_id = result.scalar()
            if not resp_id:
                raise RuntimeError(
                    f"Could not obtain Response row for survey={survey_id} user={user_id}"
                )

    # 2. Upsert the Answer row
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
    Uses a LEFT OUTER JOIN + IS NULL to find gaps in one round-trip.
    """
    from models import Question, Answer, Response
    from sqlalchemy import select

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
    from sqlalchemy import select, func

    result = await session.execute(
        select(func.count()).select_from(Question).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0


async def get_response_count(session: AsyncSession, survey_id: int) -> int:
    """Return the number of unique respondents for a survey."""
    from models import Response
    from sqlalchemy import select, func

    result = await session.execute(
        select(func.count()).select_from(Response).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0
