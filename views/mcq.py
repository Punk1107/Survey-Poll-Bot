import discord
from database import get_session, upsert_answer, get_next_question
import utils


class MCQView(discord.ui.View):
    def __init__(
        self,
        survey_id: int,
        question_id: int,
        options: list[str],
        user_id: str,
        question_num: int = 0,
        total: int = 0,
    ):
        super().__init__(timeout=180)
        self.survey_id    = survey_id
        self.question_id  = question_id
        self.user_id      = user_id
        self.question_num = question_num
        self.total        = total

        placeholder = "Choose an option…"
        if question_num and total:
            placeholder = f"Q {question_num}/{total} — Choose an option"

        self.add_item(
            MCQSelect(
                survey_id=survey_id,
                question_id=question_id,
                options=options,
                parent=self,
                placeholder=placeholder,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "❌ This question is not for you.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        try:
            # We don't have the message object here easily, but we can stop the view.
            # Usually views are used with a specific interaction.
            # If we want to edit the message on timeout, we'd need to store it.
            # For now, disabling children is a good baseline.
            pass
        except Exception:
            pass
        self.stop()


class MCQSelect(discord.ui.Select):
    def __init__(
        self,
        survey_id: int,
        question_id: int,
        options: list[str],
        parent: MCQView,
        placeholder: str,
    ):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=o[:100], value=o[:100])
                for o in options
            ],
        )
        self.survey_id   = survey_id
        self.question_id = question_id
        self.parent      = parent

    async def callback(self, interaction: discord.Interaction):
        answer_val = self.values[0]

        async with get_session() as session:
            await upsert_answer(
                session=session,
                survey_id=self.survey_id,
                question_id=self.question_id,
                user_id=str(interaction.user.id),
                answer_value=answer_val,
            )
            next_q = await get_next_question(
                session=session,
                survey_id=self.survey_id,
                user_id=str(interaction.user.id),
            )

        await utils.send_question_ui(
            interaction=interaction,
            survey_id=self.survey_id,
            question=next_q,
            user_id=str(interaction.user.id),
            current_num=self.parent.question_num + 1 if next_q else self.parent.question_num,
            total=self.parent.total,
            is_edit=True,
        )
