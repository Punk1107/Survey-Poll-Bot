import discord
from database import get_session, upsert_answer, get_next_question
import utils

# Rating emoji labels per value
_RATING_EMOJI = {
    1:  "⭐",
    2:  "⭐⭐",
    3:  "⭐⭐⭐",
    4:  "⭐⭐⭐⭐",
    5:  "⭐⭐⭐⭐⭐",
    6:  "6",
    7:  "7",
    8:  "8",
    9:  "9",
    10: "10",
}

# Button colors: 1-3 green, 4-7 blurple, 8-10 red (difficulty gradient)
def _button_style(value: int) -> discord.ButtonStyle:
    if value <= 3:
        return discord.ButtonStyle.success
    if value <= 7:
        return discord.ButtonStyle.primary
    return discord.ButtonStyle.danger


class RatingView(discord.ui.View):
    def __init__(
        self,
        survey_id: int,
        question_id: int,
        user_id: str,
        question_num: int = 0,
        total: int = 0,
        scale: int = 5,         # 5 or 10
    ):
        super().__init__(timeout=180)
        self.survey_id    = survey_id
        self.question_id  = question_id
        self.user_id      = user_id
        self.question_num = question_num
        self.total        = total

        for i in range(1, scale + 1):
            self.add_item(
                RatingButton(
                    value=i,
                    label=_RATING_EMOJI.get(i, str(i)),
                    style=_button_style(i),
                    parent=self,
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
        self.stop()


class RatingButton(discord.ui.Button):
    def __init__(self, value: int, label: str, style: discord.ButtonStyle, parent: RatingView):
        super().__init__(label=label, style=style)
        self.value  = value
        self.parent = parent

    async def callback(self, interaction: discord.Interaction):
        async with get_session() as session:
            await upsert_answer(
                session=session,
                survey_id=self.parent.survey_id,
                question_id=self.parent.question_id,
                user_id=str(interaction.user.id),
                answer_value=str(self.value),
            )
            next_q = await get_next_question(
                session=session,
                survey_id=self.parent.survey_id,
                user_id=str(interaction.user.id),
            )

        await utils.send_question_ui(
            interaction=interaction,
            survey_id=self.parent.survey_id,
            question=next_q,
            user_id=str(interaction.user.id),
            current_num=self.parent.question_num + 1 if next_q else self.parent.question_num,
            total=self.parent.total,
            is_edit=True,
        )
