"""Bot factory and main entrypoint."""
from __future__ import annotations

import asyncio
import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from .config import CONFIG
from .db.mongo import Database
from .cogs.views import ConfessionView
from .utils.logging_setup import setup_logging

log = logging.getLogger(__name__)

INITIAL_COGS = (
    "bot.cogs.confessions",
    "bot.cogs.moderation",
    "bot.cogs.settings",
    "bot.cogs.stats",
)


class ConfessionBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # needed for DM listener replies
        intents.members = False
        super().__init__(command_prefix="!unused!", intents=intents, help_command=None)
        self.db = Database(CONFIG.mongo_uri, CONFIG.mongo_db)

    async def setup_hook(self) -> None:
        await self.db.connect()

        # Register persistent view so Advice / Report buttons survive restarts.
        self.add_view(ConfessionView())

        for ext in INITIAL_COGS:
            await self.load_extension(ext)
            log.info("Loaded cog %s", ext)

        if CONFIG.dev_guild_id:
            guild = discord.Object(id=CONFIG.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d commands to dev guild %s", len(synced), CONFIG.dev_guild_id)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id if self.user else "?")

    async def close(self) -> None:
        try:
            await self.db.close()
        finally:
            await super().close()


async def _on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    log.error("Slash command error: %s\n%s", error, "".join(traceback.format_exception(error)))
    msg = "Something went wrong handling that command. Please try again."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


async def main() -> None:
    setup_logging(CONFIG.log_level)
    bot = ConfessionBot()
    bot.tree.on_error = _on_app_command_error  # type: ignore[assignment]
    async with bot:
        await bot.start(CONFIG.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
