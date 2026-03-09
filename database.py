import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncConnection
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
    # StaticPool keeps a single connection for SQLite — needed for WAL + in-memory DBs.
    # For file-based SQLite the pool defaults are fine, but we tune them explicitly.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(async_db_url, **_engine_kwargs)


# ── Schema migrations ────────────────────────────────────────────────────────
async def run_migrations() -> None:
    """
    Add any columns that exist in the ORM models but are missing from the
    live database (SQLite's CREATE TABLE … IF NOT EXISTS won't add new columns
    to an existing table, so we handle that here explicitly).
    """
    # Each entry: (table, column, DDL type, default expression)
    _pending: list[tuple[str, str, str, str]] = [
        ("surveys", "description",   "TEXT",    "NULL"),
        ("surveys", "max_responses", "INTEGER", "NULL"),
        ("questions", "order",       "INTEGER", "0"),
    ]

    async with engine.begin() as conn:
        for table, column, col_type, default in _pending:
            # PRAGMA table_info returns one row per column
            rows = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in rows}   # index 1 = column name
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
    WAL mode → massively improves concurrent read/write throughput.
    foreign_keys=ON → enforce referential integrity at the DB level.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")   # safe + faster than FULL
    cursor.execute("PRAGMA cache_size=-32000")    # 32 MB page cache
    cursor.close()


# ── Session factory ─────────────────────────────────────────────────────────
_AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,   # explicit flush gives us control; avoids accidental DB hits
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that provides a scoped AsyncSession.
    Rolls back on exception; always closes the session.

    Usage:
        async with get_session() as session:
            ...
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
    """
    from models import Response, Answer
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    # 1. Get-or-create the Response row
    result = await session.execute(
        select(Response).filter_by(survey_id=survey_id, user_id=user_id)
    )
    response = result.scalars().first()

    if not response:
        response = Response(survey_id=survey_id, user_id=user_id)
        session.add(response)
        try:
            await session.flush()   # get the ID without a full commit
        except IntegrityError:
            # Race: another coroutine committed first — fetch the existing row
            await session.rollback()
            result = await session.execute(
                select(Response).filter_by(survey_id=survey_id, user_id=user_id)
            )
            response = result.scalars().first()

    # 2. Upsert the Answer row
    result = await session.execute(
        select(Answer).filter_by(response_id=response.id, question_id=question_id)
    )
    existing = result.scalars().first()

    if existing:
        existing.answer = str(answer_value)
        is_update = True
    else:
        session.add(
            Answer(response_id=response.id, question_id=question_id, answer=str(answer_value))
        )
        is_update = False

    # Caller's context manager will commit
    return answer_value, is_update


async def get_next_question(session: AsyncSession, survey_id: int, user_id: str):
    """
    Return the next unanswered Question for a user in a survey, ordered by
    (question.order, question.id).  Returns None when all questions answered.
    """
    from models import Question, Answer, Response
    from sqlalchemy import select

    # 1. Check for existing response
    result = await session.execute(
        select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
    )
    response_id = result.scalar()

    # 2. All questions for the survey, ordered deterministically
    result = await session.execute(
        select(Question)
        .filter_by(survey_id=survey_id)
        .order_by(Question.order, Question.id)
    )
    questions = result.scalars().all()

    if not questions:
        return None

    if not response_id:
        return questions[0]

    # 3. Set of already-answered question IDs
    result = await session.execute(
        select(Answer.question_id).filter_by(response_id=response_id)
    )
    answered_ids = set(result.scalars().all())

    # 4. First unanswered
    for q in questions:
        if q.id not in answered_ids:
            return q

    return None  # all done


async def get_question_count(session: AsyncSession, survey_id: int) -> int:
    """Return the total number of questions for a survey."""
    from models import Question
    from sqlalchemy import select, func

    result = await session.execute(
        select(func.count()).select_from(Question).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0


async def get_response_count(session: AsyncSession, survey_id: int) -> int:
    """Return the number of distinct users who have responded."""
    from models import Response
    from sqlalchemy import select, func

    result = await session.execute(
        select(func.count()).select_from(Response).filter_by(survey_id=survey_id)
    )
    return result.scalar() or 0
