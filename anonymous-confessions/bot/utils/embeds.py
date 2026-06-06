"""Reusable embed builders."""
from __future__ import annotations

import discord

BRAND_COLOR = 0x5865F2  # Discord blurple
DANGER_COLOR = 0xED4245
SUCCESS_COLOR = 0x57F287


def confession_embed(*, confession_id: int, content: str, category: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"🕵️ Anonymous Confession #{confession_id}",
        description=f"“{content}”",
        color=BRAND_COLOR,
    )
    embed.add_field(name="Category", value=category, inline=True)
    embed.set_footer(text="Submitted anonymously • Identity is never revealed")
    return embed


def advice_embed(*, advice_number: int, content: str) -> discord.Embed:
    return discord.Embed(
        title=f"💡 Advice #{advice_number}",
        description=content,
        color=SUCCESS_COLOR,
    ).set_footer(text="Posted anonymously")


def pending_embed(*, confession_id: int, content: str, category: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"⏳ Pending Confession #{confession_id}",
        description=f"“{content}”",
        color=0xFEE75C,
    )
    embed.add_field(name="Category", value=category, inline=True)
    embed.set_footer(text="Use /approve or /reject")
    return embed


def info(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=BRAND_COLOR)


def error(description: str) -> discord.Embed:
    return discord.Embed(title="⚠️ Error", description=description, color=DANGER_COLOR)


def success(description: str) -> discord.Embed:
    return discord.Embed(title="✅ Done", description=description, color=SUCCESS_COLOR)
