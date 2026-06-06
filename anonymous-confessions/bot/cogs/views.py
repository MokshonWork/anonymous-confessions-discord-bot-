"""Persistent UI: ConfessionView (Advice + Report buttons) and modals."""
from __future__ import annotations

import logging

import discord

from ..utils import embeds, security

log = logging.getLogger(__name__)


class AdviceModal(discord.ui.Modal, title="Give Advice"):
    advice = discord.ui.TextInput(
        label="Your advice",
        style=discord.TextStyle.paragraph,
        placeholder="Be kind. Be helpful. You're anonymous too.",
        min_length=4,
        max_length=1000,
        required=True,
    )

    def __init__(self, confession_id: int) -> None:
        super().__init__(timeout=600)
        self.confession_id = confession_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        db = bot.db  # type: ignore[attr-defined]
        text = str(self.advice.value).strip()

        if security.is_hard_blocked(text) or security.contains_profanity(text):
            text = security.censor(text)

        confession = await db.get_confession(self.confession_id)
        if not confession or confession.get("status") != "posted":
            await interaction.response.send_message(
                embed=embeds.error("That confession is no longer available."),
                ephemeral=True,
            )
            return

        thread_id = confession.get("thread_id")
        thread = bot.get_channel(thread_id) if thread_id else None
        if thread is None and thread_id:
            try:
                thread = await bot.fetch_channel(thread_id)
            except discord.HTTPException:
                thread = None

        if thread is None:
            await interaction.response.send_message(
                embed=embeds.error("Could not find the discussion thread for this confession."),
                ephemeral=True,
            )
            return

        advice_number = await db.add_advice(
            self.confession_id, interaction.user.id, text
        )

        await thread.send(embed=embeds.advice_embed(advice_number=advice_number, content=text))
        await interaction.response.send_message(
            embed=embeds.success("Your advice has been posted anonymously."),
            ephemeral=True,
        )


class ReportModal(discord.ui.Modal, title="Report Confession"):
    reason = discord.ui.TextInput(
        label="Why are you reporting this?",
        style=discord.TextStyle.paragraph,
        placeholder="E.g. harassment, doxxing, slurs…",
        min_length=4,
        max_length=500,
        required=True,
    )

    def __init__(self, confession_id: int) -> None:
        super().__init__(timeout=600)
        self.confession_id = confession_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        db = bot.db  # type: ignore[attr-defined]
        await db.add_report(self.confession_id, interaction.user.id, str(self.reason.value).strip())

        # Notify mod channel if configured
        if interaction.guild:
            settings = await db.get_guild_settings(interaction.guild.id)
            mod_channel_id = settings.get("mod_channel_id")
            if mod_channel_id:
                ch = interaction.guild.get_channel(mod_channel_id)
                if isinstance(ch, (discord.TextChannel, discord.Thread)):
                    await ch.send(
                        embed=embeds.info(
                            f"🚩 Report on Confession #{self.confession_id}",
                            f"**Reason:** {self.reason.value}\n"
                            f"**Reporter:** {interaction.user.mention} (`{interaction.user.id}`)",
                        )
                    )

        await interaction.response.send_message(
            embed=embeds.success("Thanks — moderators have been notified."),
            ephemeral=True,
        )


class ConfessionView(discord.ui.View):
    """Persistent view attached to every posted confession."""

    def __init__(self, confession_id: int | None = None) -> None:
        super().__init__(timeout=None)
        self.confession_id = confession_id

    @staticmethod
    async def _resolve_confession_id(interaction: discord.Interaction) -> int | None:
        """Look up the confession by the message the button is on."""
        bot = interaction.client
        db = bot.db  # type: ignore[attr-defined]
        if interaction.message is None:
            return None
        doc = await db.get_confession_by_message(interaction.message.id)
        return int(doc["confession_id"]) if doc else None

    @discord.ui.button(
        label="Give Advice",
        emoji="💡",
        style=discord.ButtonStyle.primary,
        custom_id="confession:advice",
    )
    async def advice_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        cid = await self._resolve_confession_id(interaction)
        if cid is None:
            await interaction.response.send_message(
                embed=embeds.error("This confession is no longer tracked."), ephemeral=True
            )
            return
        await interaction.response.send_modal(AdviceModal(cid))

    @discord.ui.button(
        label="Report",
        emoji="🚩",
        style=discord.ButtonStyle.danger,
        custom_id="confession:report",
    )
    async def report_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        cid = await self._resolve_confession_id(interaction)
        if cid is None:
            await interaction.response.send_message(
                embed=embeds.error("This confession is no longer tracked."), ephemeral=True
            )
            return
        await interaction.response.send_modal(ReportModal(cid))


# ---------------------------------------------------------------------------
# Confess modal (used by /confess)
# ---------------------------------------------------------------------------

REACTION_EMOJIS = ["❤️", "😂", "😮", "💡", "🔥"]


class ConfessModal(discord.ui.Modal, title="Anonymous Confession"):
    content = discord.ui.TextInput(
        label="Your confession",
        style=discord.TextStyle.paragraph,
        placeholder="Speak your truth. No one will know it's you.",
        min_length=10,
        max_length=1500,
        required=True,
    )

    def __init__(self, submit_callback) -> None:
        super().__init__(timeout=600)
        self._submit_callback = submit_callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._submit_callback(interaction, str(self.content.value).strip())
