from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

# Fix sqlite URL for aiosqlite: sqlite:///... -> sqlite+aiosqlite:///...
async_db_url = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(
    async_db_url,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def get_session() -> AsyncSession:
    return AsyncSessionLocal()

async def upsert_answer(session: AsyncSession, survey_id: int, question_id: int, user_id: str, answer_value: str) -> tuple[str, bool]:
    from models import Response, Answer
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    
    # 1. Get or create response object
    result = await session.execute(
        select(Response).filter_by(survey_id=survey_id, user_id=user_id)
    )
    response = result.scalars().first()

    if not response:
        try:
            response = Response(survey_id=survey_id, user_id=user_id)
            session.add(response)
            await session.commit()
            await session.refresh(response)
        except IntegrityError:
            await session.rollback()
            result = await session.execute(
                select(Response).filter_by(survey_id=survey_id, user_id=user_id)
            )
            response = result.scalars().first()

    # 2. Upsert answer
    result = await session.execute(
        select(Answer).filter_by(response_id=response.id, question_id=question_id)
    )
    existing_answer = result.scalars().first()

    is_update = False
    if existing_answer:
        existing_answer.answer = str(answer_value)
        is_update = True
    else:
        session.add(Answer(response_id=response.id, question_id=question_id, answer=str(answer_value)))
    
    await session.commit()
    return answer_value, is_update

async def get_next_question(session: AsyncSession, survey_id: int, user_id: str):
    from models import Question, Answer, Response
    from sqlalchemy import select, and_
    
    # 1. Get the response ID if it exists
    result = await session.execute(
        select(Response.id).filter_by(survey_id=survey_id, user_id=user_id)
    )
    response_id = result.scalar()

    # 2. Get all question IDs for this survey
    questions_query = select(Question).filter_by(survey_id=survey_id).order_by(Question.id)
    result = await session.execute(questions_query)
    questions = result.scalars().all()

    if not questions:
        return None

    if not response_id:
        # No response yet, return the first question
        return questions[0]

    # 3. Get all answered question IDs
    answered_query = select(Answer.question_id).filter_by(response_id=response_id)
    result = await session.execute(answered_query)
    answered_ids = set(result.scalars().all())

    # 4. Find the first unanswered question
    for q in questions:
        if q.id not in answered_ids:
            return q
            
    # All answered
    return None
