"""Per-guild settings: confession channel, mod channel."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..utils import embeds


def _is_admin(interaction: discord.Interaction) -> bool:
    perms = interaction.user.guild_permissions if isinstance(interaction.user, discord.Member) else None
    return bool(perms and (perms.administrator or perms.manage_guild))


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="setchannel", description="(Admin) Set the channel where confessions are posted.")
    @app_commands.describe(channel="Text channel to post confessions in")
    async def setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return

        # Sanity check: bot needs to be able to talk + create threads there.
        me = interaction.guild.me
        perms = channel.permissions_for(me) if me else None
        if perms is None or not (perms.send_messages and perms.embed_links):
            await interaction.response.send_message(
                embed=embeds.error(
                    f"I need **Send Messages** and **Embed Links** in {channel.mention}."
                ),
                ephemeral=True,
            )
            return

        await self.bot.db.set_confession_channel(interaction.guild.id, channel.id)  # type: ignore[attr-defined]
        await interaction.response.send_message(
            embed=embeds.success(f"Confessions will now be posted in {channel.mention}."),
            ephemeral=True,
        )

    @app_commands.command(name="setmodchannel", description="(Admin) Set the channel where reports and pending confessions appear.")
    @app_commands.describe(channel="Text channel for moderator notifications")
    async def setmodchannel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not _is_admin(interaction) or interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Admin only."), ephemeral=True
            )
            return
        await self.bot.db.set_mod_channel(interaction.guild.id, channel.id)  # type: ignore[attr-defined]
        await interaction.response.send_message(
            embed=embeds.success(f"Moderator notifications will go to {channel.mention}."),
            ephemeral=True,
        )

    @app_commands.command(name="settings", description="View this server's confession settings.")
    async def settings(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Use this in a server."), ephemeral=True
            )
            return
        s = await self.bot.db.get_guild_settings(interaction.guild.id)  # type: ignore[attr-defined]
        ch_id = s.get("confession_channel_id")
        mod_id = s.get("mod_channel_id")
        embed = embeds.info(
            "🛠️ Confession Settings",
            f"**Confession channel:** {('<#' + str(ch_id) + '>') if ch_id else '*not set — run /setchannel*'}\n"
            f"**Mod channel:** {('<#' + str(mod_id) + '>') if mod_id else '*not set*'}",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
