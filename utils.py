import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Question, Choice

async def send_question_ui(
    interaction: discord.Interaction,
    session: AsyncSession,
    survey_id: int,
    question: Question,
    is_edit: bool = False
):
    """
    Renders the question UI (View or Modal) for a given question.
    """
    if not question:
        content = "🎉 **Survey Completed!** Thank you for your responses."
        if is_edit:
            await interaction.response.edit_message(content=content, view=None)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(content, ephemeral=True)
            else:
                await interaction.followup.send(content, ephemeral=True)
        return

    # Fetch choices if MCQ
    view = None
    if question.qtype == "mcq":
        from views.mcq import MCQView
        result = await session.execute(select(Choice).filter_by(question_id=question.id))
        choices = result.scalars().all()
        view = MCQView(survey_id, question.id, [c.text for c in choices])
        content = f"📋 **{question.text}**"
    elif question.qtype == "rating":
        from views.rating import RatingView
        view = RatingView(survey_id, question.id)
        content = f"⭐ **{question.text}**"
    elif question.qtype == "text":
        from views.text import TextPromptView, TextModal
        modal = TextModal(survey_id, question.id, question.text)
        if not is_edit and not interaction.response.is_done():
            # If it's a new interaction, we can pop the modal directly
            await interaction.response.send_modal(modal)
            return
        else:
            # If it's an edit, we can't send a modal. Send a button instead.
            view = TextPromptView(survey_id, question.id, question.text)
            content = f"📝 **{question.text}**\n*(Click the button below to type your answer)*"

    if view:
        if is_edit and not interaction.response.is_done():
            await interaction.response.edit_message(content=content, view=view)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(content, view=view, ephemeral=True)
            else:
                await interaction.edit_original_response(content=content, view=view)
