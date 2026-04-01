import logging

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Question, Choice

log = logging.getLogger(__name__)

# Question-type colours
_QTYPE_COLOR = {
    "mcq":    discord.Color.blurple(),
    "rating": discord.Color.gold(),
    "text":   discord.Color.green(),
}


def _progress_bar(current: int, total: int, width: int = 10) -> str:
    """Return e.g. '████████░░  4/5'."""
    if total == 0:
        return ""
    filled = round(width * current / total)
    return "█" * filled + "░" * (width - filled) + f"  {current}/{total}"


def _question_embed(question: Question, current_num: int, total: int) -> discord.Embed:
    """Build a rich Embed for a survey question."""
    qtype_labels = {"mcq": "Single Choice", "rating": "Rating", "text": "Text"}
    color = _QTYPE_COLOR.get(question.qtype, discord.Color.blurple())

    embed = discord.Embed(
        description=f"**{question.text}**",
        color=color,
    )
    embed.set_author(name=f"📋 Question {current_num} of {total}")

    if total > 0:
        embed.set_footer(text=_progress_bar(current_num, total))

    embed.add_field(
        name="Type",
        value=f"`{qtype_labels.get(question.qtype, question.qtype)}`",
        inline=True,
    )

    return embed


async def send_question_ui(
    interaction: discord.Interaction,
    survey_id: int,
    question: Question | None,
    user_id: str,
    current_num: int = 0,
    total: int = 0,
    is_edit: bool = False,
):
    """
    Render the question UI (View or Modal) for a given question.
    When question is None, shows the completion message.
    """
    # ── Survey complete ──────────────────────────────────────────────────────
    if not question:
        embed = discord.Embed(
            title="🎉 Survey Completed!",
            description="Thank you for your responses. Your answers have been recorded.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=_progress_bar(total, total))

        if is_edit and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=None, content=None)
        elif interaction.response.is_done():
            try:
                await interaction.edit_original_response(embed=embed, view=None, content=None)
            except discord.NotFound:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # ── Build the embed ──────────────────────────────────────────────────────
    embed = _question_embed(question, current_num, total)

    # ── Route to the correct UI component ────────────────────────────────────
    if question.qtype == "mcq":
        from views.mcq import MCQView
        from database import get_session
        async with get_session() as session:
            result = await session.execute(
                select(Choice.text).filter_by(question_id=question.id)
            )
            choices = list(result.scalars().all())

        # BUG FIX: Discord forbids a Select with zero options. Guard here
        # so a misconfigured MCQ question gets a clear error instead of a crash.
        if not choices:
            error_embed = discord.Embed(
                title="⚠️ Question Setup Incomplete",
                description=(
                    f"The question **\"{question.text}\"** has no choices configured. "
                    "Please ask the survey creator to add choices via `/survey add-choice`."
                ),
                color=discord.Color.orange(),
            )
            await _send(interaction, embed=error_embed, view=None, is_edit=is_edit)
            return

        view = MCQView(
            survey_id=survey_id,
            question_id=question.id,
            options=choices,
            user_id=user_id,
            question_num=current_num,
            total=total,
        )
        await _send(interaction, embed=embed, view=view, is_edit=is_edit)

    elif question.qtype == "rating":
        from views.rating import RatingView
        view = RatingView(
            survey_id=survey_id,
            question_id=question.id,
            user_id=user_id,
            question_num=current_num,
            total=total,
        )
        await _send(interaction, embed=embed, view=view, is_edit=is_edit)

    elif question.qtype == "text":
        from views.text import TextModal, TextPromptView
        if not is_edit and not interaction.response.is_done():
            # Can pop modal directly on fresh interaction
            await interaction.response.send_modal(
                TextModal(
                    survey_id=survey_id,
                    question_id=question.id,
                    title=question.text,
                    question_num=current_num,
                    total=total,
                )
            )
            return
        # After an edit, send a "Click to answer" button instead
        view = TextPromptView(
            survey_id=survey_id,
            question_id=question.id,
            title=question.text,
            user_id=user_id,
            question_num=current_num,
            total=total,
        )
        await _send(interaction, embed=embed, view=view, is_edit=is_edit)

    else:
        log.warning("Unknown question type '%s' for question id=%d", question.qtype, question.id)
        unknown_embed = discord.Embed(
            title="⚠️ Unknown Question Type",
            description=f"Question type `{question.qtype}` is not supported.",
            color=discord.Color.orange(),
        )
        await _send(interaction, embed=unknown_embed, view=None, is_edit=is_edit)


async def _send(
    interaction: discord.Interaction,
    embed: discord.Embed,
    view: discord.ui.View | None,
    is_edit: bool,
):
    """Central dispatcher — handles edit vs. new message vs. followup."""
    kwargs = {"embed": embed, "view": view, "content": None}
    if is_edit and not interaction.response.is_done():
        await interaction.response.edit_message(**kwargs)
    elif interaction.response.is_done():
        try:
            await interaction.edit_original_response(**kwargs)
        except discord.NotFound:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
