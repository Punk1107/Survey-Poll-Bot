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

            action_text = "saved"
            if existing_answer:
                existing_answer.answer = self.answer.value
                action_text = "updated"
            else:
                session.add(
                    Answer(
                        response_id=response.id,
                        question_id=self.question_id,
                        answer=self.answer.value
                    )
                )
            await session.commit()

        await interaction.response.send_message(
            f"📝 Answer {action_text}",
            ephemeral=True
        )
