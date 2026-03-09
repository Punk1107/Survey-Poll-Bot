import discord
from database import get_session
from models import Response, Answer

class TextModal(discord.ui.Modal):
    def __init__(self, survey_id, question_id, title):
        super().__init__(title=title)
        self.survey_id = survey_id
        self.question_id = question_id

        self.answer = discord.ui.TextInput(label="Your answer")
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        from database import get_session, upsert_answer, get_next_question
        import utils

        async with get_session() as session:
            # 1. Save the answer
            await upsert_answer(
                session=session, 
                survey_id=self.survey_id, 
                question_id=self.question_id, 
                user_id=str(interaction.user.id), 
                answer_value=self.answer.value
            )
            
            # 2. Get next question
            next_q = await get_next_question(
                session=session, 
                survey_id=self.survey_id, 
                user_id=str(interaction.user.id)
            )

            # 3. Transition to next question
            # Since this is a modal submission, interaction.response is not yet done!
            # send_question_ui will send an ephemeral message or a new modal or edit.
            await utils.send_question_ui(
                interaction=interaction,
                session=session,
                survey_id=self.survey_id,
                question=next_q,
                is_edit=True
            )

class TextPromptView(discord.ui.View):
    def __init__(self, survey_id, question_id, title):
        super().__init__(timeout=120)
        self.survey_id = survey_id
        self.question_id = question_id
        self.title_text = title

    @discord.ui.button(label="Answer Question", style=discord.ButtonStyle.primary, emoji="📝")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            TextModal(self.survey_id, self.question_id, self.title_text)
        )
