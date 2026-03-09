import discord
from database import get_session, upsert_answer, get_next_question
import utils


class TextModal(discord.ui.Modal):
    def __init__(
        self,
        survey_id: int,
        question_id: int,
        title: str,
        question_num: int = 0,
        total: int = 0,
    ):
        # Discord modal title max = 45 chars
        super().__init__(title=title[:45])
        self.survey_id    = survey_id
        self.question_id  = question_id
        self.question_num = question_num
        self.total        = total

        self.answer = discord.ui.TextInput(
            label="Your answer",
            style=discord.TextStyle.long,
            placeholder="Type your answer here…",
            min_length=1,
            max_length=1000,
            required=True,
        )
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        async with get_session() as session:
            await upsert_answer(
                session=session,
                survey_id=self.survey_id,
                question_id=self.question_id,
                user_id=str(interaction.user.id),
                answer_value=self.answer.value,
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
            current_num=self.question_num + 1 if next_q else self.question_num,
            total=self.total,
            is_edit=True,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            f"❌ An error occurred: {error}", ephemeral=True
        )


class TextPromptView(discord.ui.View):
    """Fallback view shown when a modal can't be sent (e.g., after a button edit)."""

    def __init__(
        self,
        survey_id: int,
        question_id: int,
        title: str,
        user_id: str,
        question_num: int = 0,
        total: int = 0,
    ):
        super().__init__(timeout=180)
        self.survey_id    = survey_id
        self.question_id  = question_id
        self.title_text   = title
        self.user_id      = user_id
        self.question_num = question_num
        self.total        = total

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
        self.stop()

    @discord.ui.button(label="✍️ Type Answer", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            TextModal(
                survey_id=self.survey_id,
                question_id=self.question_id,
                title=self.title_text,
                question_num=self.question_num,
                total=self.total,
            )
        )
