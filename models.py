from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


Base = declarative_base()


class Survey(Base):
    __tablename__ = "surveys"

    id            = Column(Integer, primary_key=True)
    title         = Column(String(100), nullable=False)
    description   = Column(String(500), nullable=True)          # NEW – optional description
    creator_id    = Column(String, nullable=False, index=True)
    is_anonymous  = Column(Boolean, default=True)
    is_published  = Column(Boolean, default=False)
    is_closed     = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    max_responses = Column(Integer, nullable=True)               # NEW – auto-close after N responses
    created_at    = Column(DateTime(timezone=True), default=_utcnow)

    questions = relationship("Question", back_populates="survey",  cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="survey",  cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id        = Column(Integer, primary_key=True)
    survey_id = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    text      = Column(String, nullable=False)
    qtype     = Column(String, nullable=False)   # mcq | rating | text
    order     = Column(Integer, default=0)        # NEW – explicit ordering

    survey  = relationship("Survey",   back_populates="questions")
    choices = relationship("Choice",   back_populates="question", cascade="all, delete-orphan")
    answers = relationship("Answer",   back_populates="question", cascade="all, delete-orphan")


class Choice(Base):
    __tablename__ = "choices"

    id          = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    text        = Column(String, nullable=False)

    question = relationship("Question", back_populates="choices")


class Response(Base):
    __tablename__ = "responses"

    id           = Column(Integer, primary_key=True)
    survey_id    = Column(Integer, ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    user_id      = Column(String, nullable=True, index=True)
    submitted_at = Column(DateTime(timezone=True), default=_utcnow)

    survey  = relationship("Survey",  back_populates="responses")
    answers = relationship("Answer",  back_populates="response", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("survey_id", "user_id", name="unique_user_response"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id          = Column(Integer, primary_key=True)
    response_id = Column(Integer, ForeignKey("responses.id", ondelete="CASCADE"), index=True)
    question_id = Column(Integer, ForeignKey("questions.id",  ondelete="CASCADE"), index=True)
    answer      = Column(String)

    response = relationship("Response", back_populates="answers")
    question = relationship("Question", back_populates="answers")

    # Composite index for fast "has this user answered this question?" lookup
    __table_args__ = (
        Index("ix_answers_response_question", "response_id", "question_id"),
    )
