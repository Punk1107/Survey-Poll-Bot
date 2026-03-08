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
        from sqlalchemy import select as sql_select
        from sqlalchemy.exc import IntegrityError
        async with get_session() as session:
            result = await session.execute(
                sql_select(Response).filter_by(
                    survey_id=self.survey_id,
                    user_id=str(interaction.user.id)
                )
            )
            response = result.scalars().first()

            if not response:
                try:
                    response = Response(
                        survey_id=self.survey_id,
                        user_id=str(interaction.user.id)
                    )
                    session.add(response)
                    await session.commit()
                    await session.refresh(response)
                except IntegrityError:
                    await session.rollback()
                    result = await session.execute(
                        sql_select(Response).filter_by(
                            survey_id=self.survey_id,
                            user_id=str(interaction.user.id)
                        )
                    )
                    response = result.scalars().first()

            result = await session.execute(
                sql_select(Answer).filter_by(
                    response_id=response.id,
                    question_id=self.question_id
                )
            )
            existing_answer = result.scalars().first()

            action_text = "submitted"
            if existing_answer:
                existing_answer.answer = select.values[0]
                action_text = "updated"
            else:
                session.add(
                    Answer(
                        response_id=response.id,
                        question_id=self.question_id,
                        answer=select.values[0]
                    )
                )
            await session.commit()

        await interaction.response.send_message(
            f"✅ Answer {action_text}: **{select.values[0]}**",
            ephemeral=True
        )
