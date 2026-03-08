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
        from sqlalchemy import select as sql_select
        from sqlalchemy.exc import IntegrityError
        async with get_session() as session:
            result = await session.execute(
                sql_select(Response).filter_by(
                    survey_id=self.parent.survey_id,
                    user_id=str(interaction.user.id)
                )
            )
            response = result.scalars().first()

            if not response:
                try:
                    response = Response(
                        survey_id=self.parent.survey_id,
                        user_id=str(interaction.user.id)
                    )
                    session.add(response)
                    await session.commit()
                    await session.refresh(response)
                except IntegrityError:
                    await session.rollback()
                    result = await session.execute(
                        sql_select(Response).filter_by(
                            survey_id=self.parent.survey_id,
                            user_id=str(interaction.user.id)
                        )
                    )
                    response = result.scalars().first()
            
            result = await session.execute(
                sql_select(Answer).filter_by(
                    response_id=response.id,
                    question_id=self.parent.question_id
                )
            )
            existing_answer = result.scalars().first()

            action_text = "Rated"
            if existing_answer:
                existing_answer.answer = str(self.value)
                action_text = "Updated rating to"
            else:
                session.add(
                    Answer(
                        response_id=response.id,
                        question_id=self.parent.question_id,
                        answer=str(self.value)
                    )
                )
            await session.commit()

        await interaction.response.send_message(
            f"⭐ {action_text} {self.value}",
            ephemeral=True
        )
