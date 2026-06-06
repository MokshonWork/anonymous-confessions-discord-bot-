"""Moderation slash commands: approve / reject / delete / ban."""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ..utils import embeds
from .views import ConfessionView, REACTION_EMOJIS

log = logging.getLogger(__name__)


def _is_admin(interaction: discord.Interaction) -> bool:
    perms = interaction.user.guild_permissions if isinstance(interaction.user, discord.Member) else None
    return bool(perms and (perms.administrator or perms.manage_guild))


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ----- approve -----------------------------------------------------
    @app_commands.command(name="approve", description="(Admin) Approve a pending confession.")
    @app_commands.describe(confession_id="ID of the confession to approve")
    async def approve(self, interaction: discord.Interaction, confession_id: int) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return

        db = self.bot.db  # type: ignore[attr-defined]
        confession = await db.get_confession(confession_id)
        if not confession or confession["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                embed=embeds.error("Confession not found."), ephemeral=True
            )
            return
        if confession["status"] != "pending":
            await interaction.response.send_message(
                embed=embeds.error(f"Confession #{confession_id} is already `{confession['status']}`."),
                ephemeral=True,
            )
            return

        # Post via the ConfessionsCog helper
        cog = self.bot.get_cog("ConfessionsCog")
        if cog is None:
            await interaction.response.send_message(
                embed=embeds.error("Internal error: confession cog missing."), ephemeral=True
            )
            return

        await cog._post_confession(interaction.guild, confession)  # type: ignore[attr-defined]
        await interaction.response.send_message(
            embed=embeds.success(f"Confession #{confession_id} approved and posted."),
            ephemeral=True,
        )

    # ----- reject ------------------------------------------------------
    @app_commands.command(name="reject", description="(Admin) Reject a pending confession.")
    @app_commands.describe(confession_id="ID of the confession to reject")
    async def reject(self, interaction: discord.Interaction, confession_id: int) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        db = self.bot.db  # type: ignore[attr-defined]
        confession = await db.get_confession(confession_id)
        if not confession or confession["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                embed=embeds.error("Confession not found."), ephemeral=True
            )
            return
        await db.set_status(confession_id, "rejected")
        await interaction.response.send_message(
            embed=embeds.success(f"Confession #{confession_id} rejected."),
            ephemeral=True,
        )

    # ----- delete ------------------------------------------------------
    @app_commands.command(name="deleteconfession", description="(Admin) Delete a posted confession.")
    @app_commands.describe(confession_id="ID of the confession to delete")
    async def delete_confession(self, interaction: discord.Interaction, confession_id: int) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        db = self.bot.db  # type: ignore[attr-defined]
        confession = await db.get_confession(confession_id)
        if not confession or confession["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                embed=embeds.error("Confession not found."), ephemeral=True
            )
            return

        # Try to delete the original message
        ch = interaction.guild.get_channel(confession.get("channel_id"))
        if isinstance(ch, discord.TextChannel) and confession.get("message_id"):
            try:
                msg = await ch.fetch_message(confession["message_id"])
                await msg.delete()
            except discord.HTTPException:
                pass

        await db.set_status(confession_id, "deleted")
        await interaction.response.send_message(
            embed=embeds.success(f"Confession #{confession_id} deleted."),
            ephemeral=True,
        )

    # ----- ban / unban -------------------------------------------------
    @app_commands.command(name="banconfess", description="(Admin) Ban a user from submitting confessions.")
    @app_commands.describe(user="User to ban")
    async def banconfess(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        await self.bot.db.set_banned(user.id, True)  # type: ignore[attr-defined]
        await interaction.response.send_message(
            embed=embeds.success(f"{user.mention} can no longer submit confessions."),
            ephemeral=True,
        )

    @app_commands.command(name="unbanconfess", description="(Admin) Unban a user from submitting confessions.")
    @app_commands.describe(user="User to unban")
    async def unbanconfess(self, interaction: discord.Interaction, user: discord.User) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        await self.bot.db.set_banned(user.id, False)  # type: ignore[attr-defined]
        await interaction.response.send_message(
            embed=embeds.success(f"{user.mention} can submit confessions again."),
            ephemeral=True,
        )

    # ----- whoposted (audit log lookup; admin only) --------------------
    @app_commands.command(
        name="whoposted",
        description="(Admin) Reveal the author of a confession. USE RESPONSIBLY.",
    )
    @app_commands.describe(confession_id="ID of the confession to reveal")
    async def whoposted(self, interaction: discord.Interaction, confession_id: int) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        # Require the strictest perm to look up identities
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embeds.error("Only members with full Administrator can use this."),
                ephemeral=True,
            )
            return

        confession = await self.bot.db.get_confession(confession_id)  # type: ignore[attr-defined]
        if not confession or confession["guild_id"] != interaction.guild.id:
            await interaction.response.send_message(
                embed=embeds.error("Confession not found."), ephemeral=True
            )
            return
        log.warning(
            "AUDIT: %s (id=%s) revealed author of confession %s",
            interaction.user, interaction.user.id, confession_id,
        )
        await interaction.response.send_message(
            embed=embeds.info(
                f"Confession #{confession_id} author",
                f"<@{confession['author_id']}> (`{confession['author_id']}`)\n\n"
                "This action has been logged.",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
