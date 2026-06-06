"""Core confession submission + posting flow."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..config import CONFIG
from ..utils import embeds, security
from ..utils.categories import detect_category
from .views import ConfessionView, ConfessModal, REACTION_EMOJIS

log = logging.getLogger(__name__)


class ConfessionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------
    # /confess
    # ------------------------------------------------------------------
    @app_commands.command(name="confess", description="Submit an anonymous confession.")
    async def confess(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Use this command inside a server."), ephemeral=True
            )
            return

        # Pre-flight checks before showing the modal
        db = self.bot.db  # type: ignore[attr-defined]

        if await db.is_banned(interaction.user.id):
            await interaction.response.send_message(
                embed=embeds.error("You are banned from submitting confessions in this bot."),
                ephemeral=True,
            )
            return

        remaining = await db.remaining_cooldown(interaction.user.id, CONFIG.confession_cooldown)
        if remaining > 0:
            minutes, seconds = divmod(remaining, 60)
            await interaction.response.send_message(
                embed=embeds.error(
                    f"You're on cooldown. Try again in **{minutes}m {seconds}s**."
                ),
                ephemeral=True,
            )
            return

        settings = await db.get_guild_settings(interaction.guild.id)
        if not settings.get("confession_channel_id"):
            await interaction.response.send_message(
                embed=embeds.error(
                    "No confession channel configured. An admin must run `/setchannel` first."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(ConfessModal(self._handle_submission))

    # ------------------------------------------------------------------
    # Submission handler (shared by modal + DM listener)
    # ------------------------------------------------------------------
    async def _handle_submission(self, interaction: discord.Interaction, content: str) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Confessions must be submitted from inside a server."),
                ephemeral=True,
            )
            return

        # Validate
        if security.is_hard_blocked(content):
            await interaction.response.send_message(
                embed=embeds.error("Your confession contains content that is not allowed."),
                ephemeral=True,
            )
            return

        if security.contains_profanity(content):
            content = security.censor(content)

        chash = security.content_hash(content)
        if await db.find_duplicate(guild.id, chash):
            await interaction.response.send_message(
                embed=embeds.error("Looks like that confession was already submitted."),
                ephemeral=True,
            )
            return

        category = detect_category(content)
        status = "pending" if CONFIG.require_approval else "posted"

        confession = await db.create_confession(
            guild_id=guild.id,
            author_id=interaction.user.id,
            content=content,
            content_hash=chash,
            category=category,
            status=status,
        )
        await db.mark_confessed(interaction.user.id)

        # Approval flow
        if CONFIG.require_approval:
            await self._send_to_mod_queue(guild, confession)
            await interaction.response.send_message(
                embed=embeds.success(
                    f"Confession **#{confession['confession_id']}** submitted and is pending moderator approval."
                ),
                ephemeral=True,
            )
            return

        await self._post_confession(guild, confession)
        await interaction.response.send_message(
            embed=embeds.success(
                f"Confession **#{confession['confession_id']}** posted anonymously."
            ),
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------
    async def _post_confession(self, guild: discord.Guild, confession: dict) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        channel_id = settings.get("confession_channel_id")
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            log.warning("Confession channel missing for guild %s", guild.id)
            return

        embed = embeds.confession_embed(
            confession_id=confession["confession_id"],
            content=confession["content"],
            category=confession["category"],
        )
        view = ConfessionView(confession_id=confession["confession_id"])
        message = await channel.send(embed=embed, view=view)

        # Add baseline reactions
        for emoji in REACTION_EMOJIS:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

        # Discussion thread
        thread_id: int | None = None
        try:
            thread = await message.create_thread(
                name=f"Discussion • Confession #{confession['confession_id']}",
                auto_archive_duration=1440,
            )
            thread_id = thread.id
        except discord.HTTPException as e:
            log.warning("Failed to create thread: %s", e)

        await db.attach_message(
            confession["confession_id"],
            channel_id=channel.id,
            message_id=message.id,
            thread_id=thread_id,
        )

    async def _send_to_mod_queue(self, guild: discord.Guild, confession: dict) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        settings = await db.get_guild_settings(guild.id)
        mod_channel_id = settings.get("mod_channel_id") or settings.get("confession_channel_id")
        channel = guild.get_channel(mod_channel_id) if mod_channel_id else None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.send(
                embed=embeds.pending_embed(
                    confession_id=confession["confession_id"],
                    content=confession["content"],
                    category=confession["category"],
                )
            )

    # ------------------------------------------------------------------
    # Reaction tracking
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:  # type: ignore[union-attr]
            return
        db = self.bot.db  # type: ignore[attr-defined]
        confession = await db.get_confession_by_message(payload.message_id)
        if not confession:
            return
        await db.increment_reaction(confession["confession_id"], str(payload.emoji), 1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        db = self.bot.db  # type: ignore[attr-defined]
        confession = await db.get_confession_by_message(payload.message_id)
        if not confession:
            return
        await db.increment_reaction(confession["confession_id"], str(payload.emoji), -1)

    # ------------------------------------------------------------------
    # DM submission
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is not None:
            return
        # DM -> tell the user how to use the bot (we can't post anonymously
        # without knowing which guild to post to).
        if message.content.startswith("/"):
            return
        try:
            await message.channel.send(
                embed=embeds.info(
                    "Submit confessions in your server",
                    "Use the `/confess` slash command inside the server where you want to post. "
                    "DMs are kept private and never forwarded.",
                )
            )
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfessionsCog(bot))
