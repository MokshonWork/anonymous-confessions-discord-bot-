"""Centralised configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    discord_token: str
    dev_guild_id: int | None
    mongo_uri: str
    mongo_db: str
    confession_cooldown: int
    require_approval: bool
    log_level: str


def load_config() -> Config:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required. Copy .env.example to .env and fill it in.")

    return Config(
        discord_token=token,
        dev_guild_id=_int(os.getenv("DEV_GUILD_ID"), 0) or None,
        mongo_uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
        mongo_db=os.getenv("MONGO_DB", "anon_confessions"),
        confession_cooldown=_int(os.getenv("CONFESSION_COOLDOWN_SECONDS"), 600),
        require_approval=_bool(os.getenv("REQUIRE_APPROVAL"), False),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


CONFIG = load_config()
