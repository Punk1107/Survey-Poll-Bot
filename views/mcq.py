import logging

import discord
from database import get_session, upsert_answer, get_next_question
import utils

log = logging.getLogger(__name__)


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
        # Store the message so on_timeout can edit it to show disabled buttons
        self.message: discord.Message | None = None

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
        """Disable all components when the view times out so the UI reflects reality."""
        for item in self.children:
            item.disabled = True
        self.stop()
        # FIX: Actually edit the message to reflect the disabled state.
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass  # Message was deleted or interaction expired — nothing we can do.

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ):
        log.error("MCQView error on item %s: %s", item, error, exc_info=True)
        msg = "❌ An error occurred while processing your answer. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass


class MCQSelect(discord.ui.Select):
    def __init__(
        self,
        survey_id: int,
        question_id: int,
        options: list[str],
        parent: MCQView,
        placeholder: str,
    ):
        # FIX: Set an explicit custom_id so the select is stable across view
        # re-instantiations. Without this, Discord generates a random ID per
        # instance, breaking any persistent-view recovery.
        # FIX: Discord hard-limits Select menus to 25 options — cap here.
        # FIX: SelectOption labels must be unique; deduplicate preserving order.
        seen: set[str] = set()
        unique_options: list[str] = []
        for o in options[:25]:
            label = o[:100]
            if label not in seen:
                seen.add(label)
                unique_options.append(label)

        super().__init__(
            custom_id=f"mcq_{survey_id}_{question_id}",
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=label, value=label)
                for label in unique_options
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
