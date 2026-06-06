"""Statistics and help commands."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from ..utils import embeds


class StatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="stats", description="Show confession statistics for this server.")
    async def stats(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=embeds.error("Use this in a server."), ephemeral=True
            )
            return
        data = await self.bot.db.stats_for_guild(interaction.guild.id)  # type: ignore[attr-defined]
        most_reacted = data["most_reacted"]
        most_str = (
            f"#{most_reacted[0]} — {most_reacted[1]} reactions"
            if most_reacted else "—"
        )
        embed = embeds.info(
            "📊 Confession Stats",
            f"**Total confessions:** {data['total_confessions']}\n"
            f"**Total advice posts:** {data['total_advice']}\n"
            f"**Most reacted confession:** {most_str}",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="How to use the Anonymous Confessions bot.")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        embed = embeds.info(
            "🕵️ Anonymous Confessions — Help",
            "**Everyone**\n"
            "`/confess` — submit an anonymous confession\n"
            "`/stats` — see server-wide confession stats\n"
            "`/settings` — view current bot settings\n"
            "`/help` — this message\n\n"
            "**Admins**\n"
            "`/setchannel` — pick the channel confessions are posted in\n"
            "`/setmodchannel` — pick a channel for reports & pending items\n"
            "`/approve` `/reject` `/deleteconfession`\n"
            "`/banconfess` `/unbanconfess`\n"
            "`/whoposted` — (audited) look up the author of a confession\n\n"
            "Use **💡 Give Advice** and **🚩 Report** buttons under each confession. "
            "Discussion happens in the auto-created thread.",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatsCog(bot))
