import discord
from discord.ext import commands
from discord import app_commands
from sqlalchemy import select
import os

from config import DISCORD_TOKEN
from database import engine, get_session
from models import Base, Survey, Question, Choice
from views.mcq import MCQView
from views.rating import RatingView
from views.text import TextModal
from analytics import mcq_stats, rating_stats, text_answers
from export import export_csv, export_json

# =====================
# BOT SETUP
# =====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# We will initialize DB in on_ready for async engines if needed, or rely on run_sync.
# Base.metadata.create_all(bind=engine) will not work synchronously for async engine.
# We will do this in an async function before bot runs or setup hook.

# =====================
# TRANSFORMERS
# =====================
class SurveyTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_session() as session:
            result = await session.execute(
                select(Survey).filter(Survey.title.ilike(f"%{current}%")).limit(25)
            )
            surveys = result.scalars().all()

        return [
            app_commands.Choice(
                name=f"{s.id} | {s.title}",
                value=str(s.id)
            )
            for s in surveys
        ]

    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        return int(value)


class QuestionTransformer(app_commands.Transformer):
    async def autocomplete(self, interaction: discord.Interaction, current: str):
        async with get_session() as session:
            result = await session.execute(
                select(Question).filter(Question.text.ilike(f"%{current}%")).limit(25)
            )
            questions = result.scalars().all()

        return [
            app_commands.Choice(
                name=f"{q.id} | {q.text[:80]}",
                value=str(q.id)
            )
            for q in questions
        ]

    async def transform(self, interaction: discord.Interaction, value: str) -> int:
        return int(value)

# =====================
# READY
# =====================
@bot.event
async def on_ready():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bot.tree.sync()
    print(f"✅ Bot ready as {bot.user}")

# =====================
# ERROR HANDLER
# =====================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Command Error: {error}")
    if interaction.response.is_done():
        await interaction.followup.send(f"❌ Error: {str(error)}", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Error: {str(error)}", ephemeral=True)

# =====================
# COMMAND GROUP
# =====================
survey = app_commands.Group(
    name="survey",
    description="Survey & Poll system"
)
bot.tree.add_command(survey)

# =====================
# /survey create
# =====================
@survey.command(name="create", description="Create a new survey")
async def survey_create(
    interaction: discord.Interaction,
    title: str,
    anonymous: bool
):
    async with get_session() as session:
        survey = Survey(
            title=title,
            creator_id=str(interaction.user.id),
            is_anonymous=anonymous,
            is_published=False,
            is_closed=False
        )
        session.add(survey)
        await session.commit()
        await session.refresh(survey)

        survey_id = survey.id
        survey_title = survey.title

        # Private confirmation to creator
        await interaction.response.send_message(
            f"✅ สร้างแบบสอบถามเรียบร้อย\n"
            f"🆔 ID: `{survey_id}`\n"
            f"👉 ต่อไป: `/survey add-question`",
            ephemeral=True
        )
        
        # Public announcement
        await interaction.followup.send(
            f"📢 **มีแบบสอบถามใหม่**\n"
            f"📋 {survey_title}\n"
            f"👤 โดย {interaction.user.mention}"
        )

# =====================
# /survey add-question
# =====================
@survey.command(name="add-question", description="Add a question to a survey")
@app_commands.choices(
    qtype=[
        app_commands.Choice(name="Single choice", value="mcq"),
        app_commands.Choice(name="Rating (1–5)", value="rating"),
        app_commands.Choice(name="Text answer", value="text"),
    ]
)
async def add_question(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
    text: str,
    qtype: app_commands.Choice[str]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey or survey.is_closed:
            await interaction.response.send_message(
                "❌ Survey not found or closed",
                ephemeral=True
            )
            return

        question = Question(
            survey_id=survey.id,
            text=text,
            qtype=qtype.value
        )
        session.add(question)
        await session.commit()

        # Private confirmation to creator
        await interaction.response.send_message(
            f"✅ เพิ่มคำถามเรียบร้อย\n"
            f"👉 ถ้าเป็น MCQ: `/survey add-choice`",
            ephemeral=True
        )
        
        # Public announcement
        await interaction.followup.send(
            f"📢 **มีคำถามใหม่ในแบบสอบถาม**\n"
            f"📋 {survey.title}\n"
            f"❓ {text}\n"
            f"👤 โดย {interaction.user.mention}"
        )

# =====================
# /survey add-choice
# =====================
@survey.command(name="add-choice", description="Add choice to a question")
async def add_choice(
    interaction: discord.Interaction,
    question_id: app_commands.Transform[int, QuestionTransformer],
    text: str
):
    async with get_session() as session:
        question = await session.get(Question, question_id)
        if not question or question.qtype != "mcq":
            await interaction.response.send_message(
                "❌ This question is not multiple-choice",
                ephemeral=True
            )
            return

        choice = Choice(
            question_id=question.id,
            text=text
        )
        session.add(choice)
        await session.commit()

        # Get count using select and count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(Choice).filter_by(question_id=question.id)
        result = await session.execute(count_query)
        count = result.scalar()

        # Private confirmation to creator
        await interaction.response.send_message(
            f"✅ เพิ่มตัวเลือกเรียบร้อย\n"
            f"ตอนนี้มี **{count} ตัวเลือก**",
            ephemeral=True
        )
        
        # Public announcement
        await interaction.followup.send(
            f"📢 **มีตัวเลือกใหม่**\n"
            f"❓ {question.text}\n"
            f"➕ {text}\n"
            f"👤 โดย {interaction.user.mention}"
        )

# =====================
# /survey preview
# =====================
@survey.command(name="preview", description="Preview a survey")
async def preview(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return

        result = await session.execute(select(Question).filter_by(survey_id=survey.id))
        questions = result.scalars().all()

        embed = discord.Embed(
            title=f"📋 {survey.title}",
            description="Survey Preview",
            color=discord.Color.blue()
        )

        if not questions:
            embed.add_field(
                name="No questions yet",
                value="Use `/survey add-question`",
                inline=False
            )

        for i, q in enumerate(questions, start=1):
            embed.add_field(
                name=f"{i}. {q.text}",
                value=f"Type: `{q.qtype}`",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# =====================
# /survey publish
# =====================
@survey.command(name="publish", description="Publish a survey")
async def publish(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return

        survey.is_published = True
        await session.commit()

        # Private confirmation to creator
        await interaction.response.send_message(
            f"✅ เผยแพร่แบบสอบถามเรียบร้อย",
            ephemeral=True
        )
        
        # Public announcement
        await interaction.followup.send(
            f"🚀 **แบบสอบถามเปิดให้ตอบแล้ว!**\n"
            f"📋 {survey.title}\n"
            f"👉 พิมพ์ `/survey answer` เพื่อตอบ\n"
            f"👤 โดย {interaction.user.mention}"
        )

# =====================
# /survey answer
# =====================
@survey.command(name="answer", description="Answer a survey")
async def answer(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey or not survey.is_published or survey.is_closed:
            await interaction.response.send_message(
                "❌ Survey is not available",
                ephemeral=True
            )
            return

        from database import get_next_question
        import utils
        
        next_q = await get_next_question(
            session=session,
            survey_id=survey.id,
            user_id=str(interaction.user.id)
        )

        if not next_q:
            # Maybe they haven't started, or there are no questions
            result = await session.execute(
                select(Question).filter_by(survey_id=survey.id)
            )
            has_questions = result.scalars().first()
            if not has_questions:
                await interaction.response.send_message(
                    "❌ Survey has no questions",
                    ephemeral=True
                )
                return
            # Otherwise, they finished the survey already
            await interaction.response.send_message(
                "🎉 **Survey Completed!** You have already answered all questions.",
                ephemeral=True
            )
            return

        await utils.send_question_ui(
            interaction=interaction,
            session=session,
            survey_id=survey.id,
            question=next_q,
            is_edit=False
        )

# =====================
# /survey close
# =====================
@survey.command(name="close", description="Close a survey")
async def close(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return

        survey.is_closed = True
        await session.commit()

        # Private confirmation to creator
        await interaction.response.send_message(
            f"✅ ปิดแบบสอบถามเรียบร้อย",
            ephemeral=True
        )
        
        # Public announcement
        await interaction.followup.send(
            f"🔒 **ปิดแบบสอบถามแล้ว**\n"
            f"📋 {survey.title}\n"
            f"👤 โดย {interaction.user.mention}"
        )

# =====================
# /survey list
# =====================
@survey.command(name="list", description="List your surveys")
async def list_surveys(interaction: discord.Interaction):
    async with get_session() as session:
        result = await session.execute(
            select(Survey).filter_by(creator_id=str(interaction.user.id))
        )
        surveys = result.scalars().all()

        if not surveys:
            await interaction.response.send_message("❌ You have no surveys.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📊 Your Surveys",
            color=discord.Color.green()
        )
        for s in surveys:
            status = "🟢 Published" if s.is_published else "⚪ Draft"
            if s.is_closed:
                status = "🔴 Closed"
            embed.add_field(
                name=f"ID: {s.id} | {s.title}",
                value=f"Status: {status}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# =====================
# /survey results
# =====================
@survey.command(name="results", description="View survey results")
async def results(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return
        
        if survey.creator_id != str(interaction.user.id):
            await interaction.response.send_message("❌ Only the creator can view results", ephemeral=True)
            return

        result = await session.execute(select(Question).filter_by(survey_id=survey.id))
        questions = result.scalars().all()

    embed = discord.Embed(
        title=f"📈 Results: {survey.title}",
        color=discord.Color.purple()
    )

    for q in questions:
        if q.qtype == "mcq":
            stats = await mcq_stats(q.id)
            text = "\n".join(f"{k}: {v}" for k, v in stats.items()) or "No answers"
            embed.add_field(name=q.text, value=f"```\n{text}\n```", inline=False)
        elif q.qtype == "rating":
            stats = await rating_stats(q.id)
            if stats["count"] > 0:
                text = f"Count: {stats['count']}\nAvg: {stats['mean']} ⭐\nMin: {stats['min']} | Max: {stats['max']}"
            else:
                text = "No answers"
            embed.add_field(name=q.text, value=f"```\n{text}\n```", inline=False)
        elif q.qtype == "text":
            answers = await text_answers(q.id)
            ans_count = len(answers)
            if ans_count > 0:
                text = f"{ans_count} response(s)\n" + "\n".join(f"- {str(a)[:30]}..." for a in answers[:3])
            else:
                text = "No answers"
            embed.add_field(name=q.text, value=f"```\n{text}\n```", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# =====================
# /survey export
# =====================
@survey.command(name="export", description="Export survey results")
@app_commands.choices(
    format=[
        app_commands.Choice(name="CSV", value="csv"),
        app_commands.Choice(name="JSON", value="json"),
    ]
)
async def export_cmd(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer],
    format: app_commands.Choice[str]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return
        
        if survey.creator_id != str(interaction.user.id):
            await interaction.response.send_message("❌ Only the creator can export results", ephemeral=True)
            return

    await interaction.response.defer(ephemeral=True)

    try:
        if format.value == "csv":
            path = await export_csv(survey.id)
        else:
            path = await export_json(survey.id)

        file = discord.File(path)
        await interaction.followup.send(f"✅ Exported {format.name}", file=file)
        os.remove(path)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to export: {e}")

# =====================
# /survey delete
# =====================
@survey.command(name="delete", description="Delete a survey")
async def delete(
    interaction: discord.Interaction,
    survey_id: app_commands.Transform[int, SurveyTransformer]
):
    async with get_session() as session:
        survey = await session.get(Survey, survey_id)
        if not survey:
            await interaction.response.send_message("❌ Survey not found", ephemeral=True)
            return

        if survey.creator_id != str(interaction.user.id):
            await interaction.response.send_message("❌ Only the creator can delete", ephemeral=True)
            return

        await session.delete(survey)
        await session.commit()

        await interaction.response.send_message(
            f"🗑️ ลบแบบสอบถาม `{survey.title}` เรียบร้อย",
            ephemeral=True
        )

# =====================
# RUN
# =====================
bot.run(DISCORD_TOKEN)
