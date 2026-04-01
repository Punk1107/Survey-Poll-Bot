"""
Survey Poll Bot — bot.py
Comprehensive Discord slash-command bot for creating, managing, and answering surveys.
"""

import logging
import os
import sys

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, func

from config import DISCORD_TOKEN, LOG_LEVEL
from database import (
    engine,
    get_session,
    get_question_count,
    get_response_count,
    run_migrations,
)
from models import Base, Survey, Question, Choice
from views.mcq import MCQView
from views.rating import RatingView
from views.text import TextModal, TextPromptView
from analytics import mcq_stats, rating_stats, text_answers, build_mcq_field, build_rating_field
from export import export_csv, export_json
from database import get_next_question
import utils
from webserver import WebServer

# =====================
# LOGGING SETUP
# =====================
# config.py guarantees LOG_LEVEL is a valid level string (defaults to INFO).
_log_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=_log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("survey_bot")

# =====================
# BOT SETUP
# =====================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Slash-command group ──────────────────────────────────────────────────────
survey = app_commands.Group(name="survey", description="Survey & Poll system")
bot.tree.add_command(survey)

# ── Web-server (keep-alive for Render / UptimeRobot) ─────────────────────────
_web = WebServer(bot)


# =====================
# SETUP HOOK  (runs once before gateway connects — correct lifecycle)
# =====================
@bot.event
async def setup_hook():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_migrations()
    log.info("Database tables created / verified.")
    # Start the keep-alive web-server so Render keeps the dyno alive
    # and UptimeRobot has an endpoint to ping.
    await _web.start()


# =====================
# ON CLOSE  (graceful shutdown)
# =====================
@bot.event
async def on_close():
    await _web.stop()


# =====================
# ON READY
# =====================
_synced = False  # Guard: only sync once across reconnects

@bot.event
async def on_ready():
    global _synced
    if not _synced:
        await bot.tree.sync()
        _synced = True
        log.info("🔄 Slash commands synced.")
    guild_count = len(bot.guilds)
    log.info("✅ Bot ready as %s | Serving %d guild(s)", bot.user, guild_count)


# =====================
# GLOBAL ERROR HANDLER
# =====================
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    cmd_name = interaction.command.name if interaction.command else "unknown"
    log.error("Command error in /%s: %s", cmd_name, error, exc_info=True)
    
    if isinstance(error, app_commands.CommandInvokeError):
        # Handle specific DB or logic errors
        original = error.original
        msg = f"❌ **Error**: {original}"
    elif isinstance(error, app_commands.CheckFailure):
        msg = f"🚫 {error}"
    else:
        msg = f"❌ **{type(error).__name__}**: {error}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass # Silent fail if interaction expired


# =====================
# TRANSFORMERS
# =====================
class SurveyTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_session() as session:
            # Optimize: only select id and title, limit results
            # ilike with index-friendly patterns if possible
            result = await session.execute(
                select(Survey.id, Survey.title)
                .filter(Survey.title.ilike(f"%{current}%"))
                .order_by(Survey.created_at.desc())
                .limit(25)
            )
            surveys = result.all()
        return [
            app_commands.Choice(name=f"{s.id} │ {s.title[:80]}", value=str(s.id))
            for s in surveys
        ]

    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise app_commands.TransformerError(value, type(self), self)


class QuestionTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: discord.Interaction, current: str):
        # Only show questions from surveys the user created, if possible
        async with get_session() as session:
            result = await session.execute(
                select(Question.id, Question.text)
                .join(Survey, Survey.id == Question.survey_id)
                .filter(
                    Question.text.ilike(f"%{current}%"),
                    Survey.creator_id == str(interaction.user.id),
                )
                .limit(25)
            )
            questions = result.all()
        return [
            app_commands.Choice(name=f"{q.id} │ {q.text[:80]}", value=str(q.id))
            for q in questions
        ]

    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise app_commands.TransformerError(value, type(self), self)


# ═══════════════════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

# ── /survey create ────────────────────────────────────────────────────────
@survey.command(name="create", description="Create a new survey")
@app_commands.describe(
    title="Survey title (max 100 chars)",
    anonymous="Hide respondent names from results",
    description="Optional short description of the survey",
)
async def survey_create(
    interaction: discord.Interaction,
    title: str,
    anonymous: bool,
    description: str | None = None,
):
    title = title.strip()
    if not title:
        await interaction.response.send_message("❌ Title cannot be empty.", ephemeral=True)
        return
    if len(title) > 100:
        await interaction.response.send_message(
            "❌ Title must be 100 characters or fewer.", ephemeral=True
        )
        return

    async with get_session() as session:
        new_survey = Survey(
            title=title,
            description=description,
            creator_id=str(interaction.user.id),
            is_anonymous=anonymous,
            is_published=False,
            is_closed=False,
        )
        session.add(new_survey)
        await session.flush()
        survey_id    = new_survey.id
        survey_title = new_survey.title

    embed = discord.Embed(
        title="✅ Survey Created",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="ID",    value=f"`{survey_id}`",          inline=True)
    embed.add_field(name="Title", value=survey_title,               inline=True)
    embed.add_field(name="Mode",  value="Anonymous" if anonymous else "Public", inline=True)
    if description:
        embed.add_field(name="Description", value=description, inline=False)
    embed.set_footer(text="Next: /survey add-question")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"📢 **New Survey: {survey_title}**\n"
        f"👤 Created by {interaction.user.mention}\n"
        f"*(Use `/survey answer` once published)*"
    )


# ── /survey add-question ──────────────────────────────────────────────────
@survey.command(name="add-question", description="Add a question to your survey")
@app_commands.describe(
    survey_id="The survey to add a question to",
    text="The question text",
    qtype="Question type",
    order="Display order (lower = earlier, default 0)",
)
@app_commands.choices(
    qtype=[
        app_commands.Choice(name="Single choice (MCQ)", value="mcq"),
        app_commands.Choice(name="Rating (1–5 stars)",  value="rating"),
        app_commands.Choice(name="Text answer",          value="text"),
    ]
)
async def add_question(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
    text: str,
    qtype: app_commands.Choice[str],
    order: int = 0,
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the survey creator can add questions.", ephemeral=True
            )
            return
        if s.is_closed:
            await interaction.response.send_message("❌ Cannot modify a closed survey.", ephemeral=True)
            return

        question = Question(survey_id=s.id, text=text, qtype=qtype.value, order=order)
        session.add(question)
        await session.flush()
        question_id = question.id
        survey_title = s.title

    embed = discord.Embed(
        title="✅ Question Added",
        description=f"**{text}**",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Type",   value=f"`{qtype.name}`", inline=True)
    embed.add_field(name="Q ID",   value=f"`{question_id}`", inline=True)
    embed.add_field(name="Survey", value=survey_title,       inline=True)
    if qtype.value == "mcq":
        embed.set_footer(text="Next: /survey add-choice to add options for this question")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"📢 **New question added to \"{survey_title}\"**\n"
        f"❓ {text} (`{qtype.name}`)\n"
        f"👤 By {interaction.user.mention}"
    )


# ── /survey add-choice ────────────────────────────────────────────────────
@survey.command(name="add-choice", description="Add an option to a multiple-choice question")
@app_commands.describe(
    question_id="The MCQ question to add a choice to",
    text="Choice text",
)
async def add_choice(
    interaction: discord.Interaction,
    question_id: app_commands.Transform[int, QuestionTransformer],
    text: str,
):
    async with get_session() as session:
        question = await session.get(Question, question_id)
        if not question:
            await interaction.response.send_message("❌ Question not found.", ephemeral=True)
            return
        if question.qtype != "mcq":
            await interaction.response.send_message(
                "❌ This question is not multiple-choice.", ephemeral=True
            )
            return

        # Verify ownership via the parent survey
        s = await session.get(Survey, question.survey_id)
        if s and s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the survey creator can add choices.", ephemeral=True
            )
            return

        choice = Choice(question_id=question.id, text=text)
        session.add(choice)
        await session.flush()

        result = await session.execute(
            select(func.count()).select_from(Choice).filter_by(question_id=question.id)
        )
        count = result.scalar() or 0
        question_text = question.text

    embed = discord.Embed(
        title="✅ Choice Added",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Question", value=question_text, inline=False)
    embed.add_field(name="Choice",   value=text,          inline=True)
    embed.add_field(name="Total",    value=f"{count} option(s)", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"📢 **New choice added**\n"
        f"❓ {question_text}\n"
        f"➕ **{text}** (now {count} option(s))\n"
        f"👤 By {interaction.user.mention}"
    )


# ── /survey preview ───────────────────────────────────────────────────────
@survey.command(name="preview", description="Preview a survey before publishing")
@app_commands.describe(survey_id="Survey to preview")
async def preview(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return

        result = await session.execute(
            select(Question).filter_by(survey_id=s.id).order_by(Question.order, Question.id)
        )
        questions = result.scalars().all()

        status_str = "⚪ Draft"
        if s.is_closed:    status_str = "🔴 Closed"
        elif s.is_published: status_str = "🟢 Published"

        embed = discord.Embed(
            title=f"📋 Preview: {s.title}",
            description=s.description or "*No description.*",
            color=discord.Color.og_blurple(),
        )
        embed.add_field(name="Status",    value=status_str,                         inline=True)
        embed.add_field(name="Mode",      value="Anonymous" if s.is_anonymous else "Public", inline=True)
        embed.add_field(name="Questions", value=str(len(questions)),                 inline=True)

        if not questions:
            embed.add_field(name="⚠️ No questions", value="Use `/survey add-question`", inline=False)
        else:
            for i, q in enumerate(questions, 1):
                qtype_label = {"mcq": "🔘 MCQ", "rating": "⭐ Rating", "text": "📝 Text"}.get(q.qtype, q.qtype)
                embed.add_field(name=f"{i}. {q.text[:80]}", value=qtype_label, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /survey publish ───────────────────────────────────────────────────────
@survey.command(name="publish", description="Publish a survey so others can answer it")
@app_commands.describe(survey_id="Survey to publish")
async def publish(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the creator can publish this survey.", ephemeral=True
            )
            return
        if s.is_closed:
            await interaction.response.send_message(
                "❌ Cannot publish a closed survey. Use `/survey reopen` first.", ephemeral=True
            )
            return

        # Guard: must have at least one question
        q_count = await get_question_count(session, s.id)
        if q_count == 0:
            await interaction.response.send_message(
                "❌ Add at least one question before publishing.", ephemeral=True
            )
            return

        s.is_published = True
        survey_title = s.title

    embed = discord.Embed(
        title="🚀 Survey Published!",
        description=f"**{survey_title}** is now open for responses.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Questions", value=str(q_count), inline=True)
    embed.set_footer(text="Respondents can use /survey answer to participate.")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"🚀 **Survey now live: {survey_title}**\n"
        f"📋 {q_count} question(s) | Use `/survey answer` to participate!\n"
        f"👤 By {interaction.user.mention}"
    )


# ── /survey answer ────────────────────────────────────────────────────────
@survey.command(name="answer", description="Answer a published survey")
@app_commands.describe(survey_id="Survey to answer")
async def answer(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    # Defer immediately to avoid the 3-second Discord timeout during DB queries
    await interaction.response.defer(ephemeral=True)

    # FIX: Merged the two separate get_session() calls into one to halve
    # round-trips and ensure consistent data across all queries.
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s or not s.is_published or s.is_closed:
            await interaction.followup.send(
                "❌ This survey is not available.", ephemeral=True
            )
            return

        q_count = await get_question_count(session, s.id)
        if q_count == 0:
            await interaction.followup.send("❌ This survey has no questions.", ephemeral=True)
            return

        next_q = await get_next_question(session, s.id, str(interaction.user.id))

        # Get all questions for numbering — reuse the same session
        result = await session.execute(
            select(Question)
            .filter_by(survey_id=survey_id)
            .order_by(Question.order, Question.id)
        )
        all_questions = result.scalars().all()

    if not next_q:
        embed = discord.Embed(
            title="🎉 Already Completed!",
            description="You have already answered all questions in this survey.",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    current_num = next((i + 1 for i, q in enumerate(all_questions) if q.id == next_q.id), 1)

    await utils.send_question_ui(
        interaction=interaction,
        survey_id=survey_id,
        question=next_q,
        user_id=str(interaction.user.id),
        current_num=current_num,
        total=q_count,
        is_edit=False,
    )


# ── /survey close ─────────────────────────────────────────────────────────
@survey.command(name="close", description="Close a survey (stops new responses)")
@app_commands.describe(survey_id="Survey to close")
async def close(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the creator can close this survey.", ephemeral=True
            )
            return

        s.is_closed    = True
        s.is_published = False
        survey_title   = s.title

    embed = discord.Embed(
        title="🔒 Survey Closed",
        description=f"**{survey_title}** is now closed.",
        color=discord.Color.red(),
    )
    embed.set_footer(text="Use /survey reopen to re-open it.")

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"🔒 **Survey closed: {survey_title}**\n"
        f"👤 By {interaction.user.mention}"
    )


# ── /survey reopen ────────────────────────────────────────────────────────
@survey.command(name="reopen", description="Reopen a closed survey")
@app_commands.describe(survey_id="Survey to reopen")
async def reopen(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the creator can reopen this survey.", ephemeral=True
            )
            return
        if not s.is_closed:
            await interaction.response.send_message(
                "ℹ️ Survey is not closed.", ephemeral=True
            )
            return

        s.is_closed    = False
        s.is_published = True
        survey_title   = s.title

    embed = discord.Embed(
        title="🔓 Survey Reopened",
        description=f"**{survey_title}** is open for responses again.",
        color=discord.Color.green(),
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)
    await interaction.followup.send(
        f"🔓 **Survey reopened: {survey_title}**\n"
        f"👤 By {interaction.user.mention}\n"
        f"Use `/survey answer` to participate!"
    )


# ── /survey list ──────────────────────────────────────────────────────────
@survey.command(name="list", description="List all surveys you created")
async def list_surveys(interaction: discord.Interaction):
    async with get_session() as session:
        result = await session.execute(
            select(Survey)
            .filter_by(creator_id=str(interaction.user.id))
            .order_by(Survey.created_at.desc())
        )
        surveys = result.scalars().all()

    if not surveys:
        await interaction.response.send_message("❌ You have no surveys yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📊 Your Surveys",
        description=f"You have **{len(surveys)}** survey(s).",
        color=discord.Color.blurple(),
    )

    for s in surveys[:20]:   # cap at 20 to keep embed within Discord limits
        if s.is_closed:
            status = "🔴 Closed"
        elif s.is_published:
            status = "🟢 Published"
        else:
            status = "⚪ Draft"

        embed.add_field(
            name=f"ID {s.id} — {s.title[:60]}",
            value=status,
            inline=True,
        )

    if len(surveys) > 20:
        embed.set_footer(text=f"Showing 20 of {len(surveys)} surveys.")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /survey info ──────────────────────────────────────────────────────────
@survey.command(name="info", description="Show full details of a survey")
@app_commands.describe(survey_id="Survey to inspect")
async def info(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return

        q_count  = await get_question_count(session, s.id)
        r_count  = await get_response_count(session, s.id)

    if s.is_closed:
        status_str = "🔴 Closed"
        color      = discord.Color.red()
    elif s.is_published:
        status_str = "🟢 Published"
        color      = discord.Color.green()
    else:
        status_str = "⚪ Draft"
        color      = discord.Color.greyple()

    embed = discord.Embed(
        title=f"📋 {s.title}",
        description=s.description or "*No description.*",
        color=color,
    )
    embed.add_field(name="Status",     value=status_str,                              inline=True)
    embed.add_field(name="Mode",       value="Anonymous" if s.is_anonymous else "Public", inline=True)
    embed.add_field(name="Creator",    value=f"<@{s.creator_id}>",                   inline=True)
    embed.add_field(name="Questions",  value=str(q_count),                            inline=True)
    embed.add_field(name="Responses",  value=str(r_count),                            inline=True)
    embed.add_field(name="Survey ID",  value=f"`{s.id}`",                             inline=True)
    embed.set_footer(text=f"Created {s.created_at.strftime('%Y-%m-%d %H:%M UTC') if s.created_at else 'unknown'}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /survey results ───────────────────────────────────────────────────────
@survey.command(name="results", description="View results for your survey")
@app_commands.describe(survey_id="Survey to view results for")
async def results(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.followup.send("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.followup.send(
                "🚫 Only the creator can view results.", ephemeral=True
            )
            return

        result = await session.execute(
            select(Question)
            .filter_by(survey_id=s.id)
            .order_by(Question.order, Question.id)
        )
        questions = result.scalars().all()
        r_count = await get_response_count(session, s.id)

    embed = discord.Embed(
        title=f"📈 Results: {s.title}",
        description=f"**{r_count}** respondent(s)",
        color=discord.Color.purple(),
    )

    for q in questions:
        if q.qtype == "mcq":
            stats = await mcq_stats(q.id)
            value = build_mcq_field(stats)
        elif q.qtype == "rating":
            stats = await rating_stats(q.id)
            value = build_rating_field(stats)
        elif q.qtype == "text":
            answers = await text_answers(q.id)
            if answers:
                previews = "\n".join(f"• {str(a)[:50]}…" if len(str(a)) > 50 else f"• {a}" for a in answers[:5])
                value = f"{len(answers)} response(s)\n{previews}"
                if len(answers) > 5:
                    value += f"\n_…and {len(answers) - 5} more_"
            else:
                value = "No answers yet."
        else:
            value = "Unknown question type."

        embed.add_field(name=f"❓ {q.text[:80]}", value=value[:1024], inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /survey export ────────────────────────────────────────────────────────
@survey.command(name="export", description="Export survey results as CSV or JSON")
@app_commands.describe(
    survey_id="Survey to export",
    fmt="Export format",
)
@app_commands.choices(
    fmt=[
        app_commands.Choice(name="CSV  (Excel-friendly)", value="csv"),
        app_commands.Choice(name="JSON (API-friendly)",   value="json"),
    ]
)
async def export_cmd(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
    fmt: app_commands.Choice[str],  # FIX: renamed from `format` — shadowed the builtin
):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.followup.send("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.followup.send(
                "🚫 Only the creator can export results.", ephemeral=True
            )
            return
        survey_title = s.title

    path: str | None = None
    try:
        if fmt.value == "csv":
            path = await export_csv(survey_id)
        else:
            path = await export_json(survey_id)

        file = discord.File(path, filename=f"{survey_title[:40]}.{fmt.value}")
        await interaction.followup.send(
            f"✅ Exported **{survey_title}** as {fmt.name}",
            file=file,
            ephemeral=True,
        )
    except Exception as e:
        log.error("Export failed for survey %d: %s", survey_id, e, exc_info=True)
        await interaction.followup.send(f"❌ Export failed: {e}", ephemeral=True)
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


# ── /survey delete ────────────────────────────────────────────────────────
class ConfirmDeleteView(discord.ui.View):
    """Confirmation dialog before permanent deletion."""

    def __init__(self, survey_id: int, survey_title: str, creator_id: str):
        super().__init__(timeout=30)
        self.survey_id    = survey_id
        self.survey_title = survey_title
        self.creator_id   = creator_id
        # Store the message so on_timeout can edit it
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the survey creator can confirm this.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """FIX: Previously had no on_timeout — the buttons stayed clickable after 30s."""
        for item in self.children:
            item.disabled = True
        self.stop()
        if self.message:
            try:
                timeout_embed = discord.Embed(
                    title="⏰ Confirmation Expired",
                    description="The deletion confirmation timed out. The survey was NOT deleted.",
                    color=discord.Color.greyple(),
                )
                await self.message.edit(embed=timeout_embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                pass

    @discord.ui.button(label="🗑️ Yes, Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with get_session() as session:
            s = await session.get(Survey, self.survey_id)
            if not s:
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="❌ Already Deleted",
                        description="This survey no longer exists.",
                        color=discord.Color.red(),
                    ),
                    view=None,
                    content=None,
                )
                self.stop()
                return
            await session.delete(s)

        log.info(
            "Survey #%d '%s' permanently deleted by user %s.",
            self.survey_id,
            self.survey_title,
            interaction.user,
        )

        success_embed = discord.Embed(
            title="🗑️ Survey Deleted",
            description=f"**{self.survey_title}** has been permanently deleted.",
            color=discord.Color.red(),
        )
        success_embed.add_field(name="Survey ID", value=f"`{self.survey_id}`", inline=True)
        success_embed.add_field(name="Deleted by", value=interaction.user.mention, inline=True)
        success_embed.set_footer(text="All questions, choices, and responses have been removed.")

        await interaction.response.edit_message(embed=success_embed, view=None, content=None)

        # Public channel announcement — consistent with close / reopen / publish
        await interaction.followup.send(
            f"🗑️ **Survey deleted: {self.survey_title}**\n"
            f"👤 Deleted by {interaction.user.mention}"
        )
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="↩️ Cancelled",
            description=f"**{self.survey_title}** was not deleted.",
            color=discord.Color.greyple(),
        )
        embed.set_footer(text="The survey and all its data remain intact.")
        await interaction.response.edit_message(embed=embed, view=None, content=None)
        self.stop()


@survey.command(name="delete", description="Permanently delete a survey")
@app_commands.describe(survey_id="Survey to delete")
async def delete(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
):
    async with get_session() as session:
        s = await session.get(Survey, survey_id)
        if not s:
            await interaction.response.send_message("❌ Survey not found.", ephemeral=True)
            return
        if s.creator_id != str(interaction.user.id):
            await interaction.response.send_message(
                "🚫 Only the creator can delete this survey.", ephemeral=True
            )
            return
        survey_title = s.title

    async with get_session() as session:
        r_count = await get_response_count(session, survey_id)
        q_count = await get_question_count(session, survey_id)

    embed = discord.Embed(
        title="⚠️ Confirm Deletion",
        description=(
            f"Are you sure you want to permanently delete **{survey_title}**?\n\n"
            "This will remove **all questions, choices, and responses**. "
            "**This cannot be undone.**"
        ),
        color=discord.Color.orange(),
    )
    embed.add_field(name="Questions", value=str(q_count), inline=True)
    embed.add_field(name="Responses", value=str(r_count), inline=True)
    embed.set_footer(text="You have 30 seconds to confirm.")
    view = ConfirmDeleteView(survey_id, survey_title, str(interaction.user.id))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    # Assign the message so ConfirmDeleteView.on_timeout can edit it.
    # fetch_message is not needed for ephemeral; use original_response.
    try:
        view.message = await interaction.original_response()
    except discord.HTTPException:
        pass


# ── /survey help ──────────────────────────────────────────────────────────
@survey.command(name="help", description="Show all available survey commands and how to use them")
async def survey_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Survey Bot — Command Reference",
        description=(
            "Welcome to **Survey Poll Bot**! 🎉\n"
            "All commands are under the `/survey` group.\n"
            "Use the autocomplete dropdown when a command asks for a **Survey ID**."
        ),
        color=discord.Color.blurple(),
    )

    # ── Setup commands ──────────────────────────────────────────────────
    embed.add_field(
        name="━━━ 🛠️  Setup ━━━",
        value="\u200b",
        inline=False,
    )
    embed.add_field(
        name="`/survey create`",
        value=(
            "Create a new survey.\n"
            "**Options:** `title` · `anonymous` · `description` *(optional)*"
        ),
        inline=False,
    )
    embed.add_field(
        name="`/survey add-question`",
        value=(
            "Add a question to your survey.\n"
            "**Types:** 🔘 Single choice (MCQ) · ⭐ Rating (1–5) · 📝 Free text"
        ),
        inline=False,
    )
    embed.add_field(
        name="`/survey add-choice`",
        value="Add an answer option to an MCQ question.",
        inline=False,
    )

    # ── Publishing commands ─────────────────────────────────────────────
    embed.add_field(
        name="━━━ 🚀  Publishing ━━━",
        value="\u200b",
        inline=False,
    )
    embed.add_field(
        name="`/survey preview`",
        value="Preview your survey before making it public (only visible to you).",
        inline=False,
    )
    embed.add_field(
        name="`/survey publish`",
        value="Open your survey so members can start answering it.",
        inline=False,
    )
    embed.add_field(
        name="`/survey close`",
        value="Close your survey and stop accepting new responses.",
        inline=False,
    )
    embed.add_field(
        name="`/survey reopen`",
        value="Reopen a previously closed survey.",
        inline=False,
    )

    # ── Participation ───────────────────────────────────────────────────
    embed.add_field(
        name="━━━ 📝  Participation ━━━",
        value="\u200b",
        inline=False,
    )
    embed.add_field(
        name="`/survey answer`",
        value="Answer a published survey. The bot will guide you through each question.",
        inline=False,
    )

    # ── Management & Results ────────────────────────────────────────────
    embed.add_field(
        name="━━━ 📊  Management & Results ━━━",
        value="\u200b",
        inline=False,
    )
    embed.add_field(
        name="`/survey list`",
        value="List all surveys you have created.",
        inline=False,
    )
    embed.add_field(
        name="`/survey info`",
        value="Show full details (status, question count, response count) for a survey.",
        inline=False,
    )
    embed.add_field(
        name="`/survey results`",
        value="View aggregated results and answer summaries for your survey.",
        inline=False,
    )
    embed.add_field(
        name="`/survey export`",
        value="Download results as a **CSV** (Excel) or **JSON** file.",
        inline=False,
    )
    embed.add_field(
        name="`/survey delete`",
        value="⚠️ Permanently delete a survey and all its data. Requires confirmation.",
        inline=False,
    )

    # ── Quick-start workflow ────────────────────────────────────────────
    embed.add_field(
        name="━━━ ⚡ Quick-Start Workflow ━━━",
        value=(
            "1️⃣ `/survey create` → give it a title\n"
            "2️⃣ `/survey add-question` → add questions (repeat as needed)\n"
            "3️⃣ `/survey add-choice` → add options for MCQ questions\n"
            "4️⃣ `/survey preview` → check everything looks right\n"
            "5️⃣ `/survey publish` → let people answer!\n"
            "6️⃣ `/survey results` or `/survey export` → see the data"
        ),
        inline=False,
    )

    embed.set_footer(text="Tip: only the survey creator can close, delete, or view results.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# =====================
# RUN
# =====================
bot.run(DISCORD_TOKEN, log_handler=None)   # log_handler=None → use our own logging config
