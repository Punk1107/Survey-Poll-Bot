import logging

import discord
from database import get_session, upsert_answer, get_next_question
import utils

log = logging.getLogger(__name__)

# Rating emoji labels per value — consistent emoji for 1-5, numeric for 6-10
_RATING_EMOJI = {
    1:  "⭐",
    2:  "⭐⭐",
    3:  "⭐⭐⭐",
    4:  "⭐⭐⭐⭐",
    5:  "⭐⭐⭐⭐⭐",
    6:  "6️⃣",
    7:  "7️⃣",
    8:  "8️⃣",
    9:  "9️⃣",
    10: "🔟",
}


def _button_style(value: int) -> discord.ButtonStyle:
    """Button colors: 1-3 green, 4-7 blurple, 8-10 red (difficulty gradient)."""
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
        # Assigned by utils._send() so on_timeout can edit the message
        self.message: discord.Message | None = None

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
        """Disable all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        self.stop()
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        log.error("RatingView error on item %s: %s", item, error, exc_info=True)
        msg = "❌ An error occurred while recording your rating. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass


class RatingButton(discord.ui.Button):
    def __init__(self, value: int, label: str, style: discord.ButtonStyle, parent: RatingView):
        # FIX: Use a stable custom_id so Discord can track this button across
        # view re-instantiations. Without this, Discord assigns a random ID per
        # instance, which can cause "unknown interaction" errors on reconnects.
        super().__init__(
            label=label,
            style=style,
            custom_id=f"rating_{parent.survey_id}_{parent.question_id}_{value}",
        )
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

        next_num = self.parent.question_num + 1 if next_q else self.parent.question_num

        await utils.send_question_ui(
            interaction=interaction,
            survey_id=self.parent.survey_id,
            question=next_q,
            user_id=str(interaction.user.id),
            current_num=next_num,
            total=self.parent.total,
            is_edit=True,
        )
