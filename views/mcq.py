import discord
from database import get_session
from models import Response, Answer

class MCQView(discord.ui.View):
    def __init__(self, survey_id, question_id, options):
        super().__init__(timeout=120)
        self.survey_id = survey_id
        self.question_id = question_id

        self.add_item(
            discord.ui.Select(
                placeholder="Choose an option",
                options=[
                    discord.SelectOption(label=o, value=o)
                    for o in options
                ]
            )
        )

    async def interaction_check(self, interaction: discord.Interaction):
        return True

    async def on_timeout(self):
        self.stop()

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select):
        from database import get_session, upsert_answer, get_next_question
        import utils

        answer_val = select.values[0]
        
        async with get_session() as session:
            # 1. Save the answer
            await upsert_answer(
                session=session, 
                survey_id=self.survey_id, 
                question_id=self.question_id, 
                user_id=str(interaction.user.id), 
                answer_value=answer_val
            )
            
            # 2. Get next question
            next_q = await get_next_question(
                session=session, 
                survey_id=self.survey_id, 
                user_id=str(interaction.user.id)
            )

            # 3. Transition to next question
            await utils.send_question_ui(
                interaction=interaction,
                session=session,
                survey_id=self.survey_id,
                question=next_q,
                is_edit=True
            )
