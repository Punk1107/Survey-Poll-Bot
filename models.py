from sqlalchemy import (
    Column, Integer, String, Boolean, Date,
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
    user_id      = Column(String, nullable=False, index=True)
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


# Server analytics deliberately stores daily aggregates only.  It never stores
# message content or message IDs.
class AnalyticsGuild(Base):
    __tablename__ = "analytics_guilds"

    guild_id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    member_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id = Column(String, ForeignKey("analytics_guilds.guild_id", ondelete="CASCADE"), primary_key=True)
    stats_channel_id = Column(String, nullable=True)
    daily_enabled = Column(Boolean, default=True, server_default="1", nullable=False)
    weekly_enabled = Column(Boolean, default=True, server_default="1", nullable=False)
    report_time = Column(String(5), default="09:00", nullable=False)
    timezone = Column(String(64), default="Asia/Bangkok", nullable=False)


class AnalyticsUser(Base):
    __tablename__ = "analytics_users"

    guild_id = Column(String, ForeignKey("analytics_guilds.guild_id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String, primary_key=True)
    display_name = Column(String(128), nullable=False)
    is_bot = Column(Boolean, default=False, nullable=False)


class AnalyticsChannel(Base):
    __tablename__ = "analytics_channels"

    guild_id = Column(String, ForeignKey("analytics_guilds.guild_id", ondelete="CASCADE"), primary_key=True)
    channel_id = Column(String, primary_key=True)
    name = Column(String(128), nullable=False)


class DailyGuildStat(Base):
    __tablename__ = "daily_guild_stats"

    guild_id = Column(String, ForeignKey("analytics_guilds.guild_id", ondelete="CASCADE"), primary_key=True)
    date = Column(Date, primary_key=True)
    messages = Column(Integer, default=0, server_default="0", nullable=False)
    active_users = Column(Integer, default=0, server_default="0", nullable=False)
    new_members = Column(Integer, default=0, server_default="0", nullable=False)
    left_members = Column(Integer, default=0, server_default="0", nullable=False)
    peak_hour = Column(Integer, nullable=True)
    __table_args__ = (Index("ix_daily_guild_stats_period", "guild_id", "date"),)


class DailyUserStat(Base):
    __tablename__ = "daily_user_stats"

    guild_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    messages = Column(Integer, default=0, server_default="0", nullable=False)
    __table_args__ = (Index("ix_daily_user_stats_lookup", "guild_id", "date", "user_id"),)


class DailyChannelStat(Base):
    __tablename__ = "daily_channel_stats"

    guild_id = Column(String, primary_key=True)
    channel_id = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    messages = Column(Integer, default=0, server_default="0", nullable=False)
    __table_args__ = (Index("ix_daily_channel_stats_lookup", "guild_id", "date", "channel_id"),)


class HourlyGuildStat(Base):
    __tablename__ = "hourly_guild_stats"

    guild_id = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    hour = Column(Integer, primary_key=True)
    messages = Column(Integer, default=0, server_default="0", nullable=False)
    __table_args__ = (Index("ix_hourly_guild_stats_period", "guild_id", "date", "hour"),)


class ReportDelivery(Base):
    __tablename__ = "analytics_report_deliveries"

    guild_id = Column(String, primary_key=True)
    report_type = Column(String(10), primary_key=True)
    period_end = Column(Date, primary_key=True)
