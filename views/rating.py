import discord
from database import get_session
from models import Response, Answer

class RatingView(discord.ui.View):
    def __init__(self, survey_id, question_id):
        super().__init__(timeout=120)
        self.survey_id = survey_id
        self.question_id = question_id

        for i in range(1, 11):
            self.add_item(RatingButton(i, self))

class RatingButton(discord.ui.Button):
    def __init__(self, value, parent):
        super().__init__(
            label=str(value),
            style=discord.ButtonStyle.primary
        )
        self.value = value
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        from database import get_session, upsert_answer, get_next_question
        import utils

        async with get_session() as session:
            # 1. Save the answer
            await upsert_answer(
                session=session, 
                survey_id=self.parent.survey_id, 
                question_id=self.parent.question_id, 
                user_id=str(interaction.user.id), 
                answer_value=str(self.value)
            )
            
            # 2. Get next question
            next_q = await get_next_question(
                session=session, 
                survey_id=self.parent.survey_id, 
                user_id=str(interaction.user.id)
            )

            # 3. Transition to next question
            await utils.send_question_ui(
                interaction=interaction,
                session=session,
                survey_id=self.parent.survey_id,
                question=next_q,
                is_edit=True
            )
