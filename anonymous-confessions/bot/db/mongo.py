"""MongoDB abstraction layer (Motor / async)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

log = logging.getLogger(__name__)


class Database:
    """Thin async wrapper around the MongoDB collections used by the bot."""

    def __init__(self, uri: str, db_name: str) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self._db: AsyncIOMotorDatabase = self._client[db_name]

    # ----- lifecycle ---------------------------------------------------------
    async def connect(self) -> None:
        await self._client.admin.command("ping")
        log.info("Connected to MongoDB database '%s'", self._db.name)
        await self._ensure_indexes()

    async def close(self) -> None:
        self._client.close()

    async def _ensure_indexes(self) -> None:
        await self.users.create_index("user_id", unique=True)
        await self.confessions.create_index("confession_id", unique=True)
        await self.confessions.create_index("author_id")
        await self.confessions.create_index("content_hash")
        await self.confessions.create_index("created_at")
        await self.advice.create_index("confession_id")
        await self.reports.create_index("confession_id")
        await self.guilds.create_index("guild_id", unique=True)
        await self.counters.create_index("name", unique=True)

    # ----- collection accessors ---------------------------------------------
    @property
    def users(self):
        return self._db["users"]

    @property
    def confessions(self):
        return self._db["confessions"]

    @property
    def advice(self):
        return self._db["advice"]

    @property
    def reports(self):
        return self._db["reports"]

    @property
    def guilds(self):
        return self._db["guilds"]

    @property
    def counters(self):
        return self._db["counters"]

    # ----- counters ----------------------------------------------------------
    async def next_sequence(self, name: str) -> int:
        doc = await self.counters.find_one_and_update(
            {"name": name},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=True,
        )
        return int(doc["value"])

    # ----- guild settings ----------------------------------------------------
    async def get_guild_settings(self, guild_id: int) -> dict[str, Any]:
        doc = await self.guilds.find_one({"guild_id": guild_id})
        return doc or {}

    async def set_confession_channel(self, guild_id: int, channel_id: int) -> None:
        await self.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"confession_channel_id": channel_id, "updated_at": _now()}},
            upsert=True,
        )

    async def set_mod_channel(self, guild_id: int, channel_id: int) -> None:
        await self.guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {"mod_channel_id": channel_id, "updated_at": _now()}},
            upsert=True,
        )

    # ----- users -------------------------------------------------------------
    async def ensure_user(self, user_id: int) -> dict[str, Any]:
        existing = await self.users.find_one({"user_id": user_id})
        if existing:
            return existing
        doc = {
            "user_id": user_id,
            "confession_count": 0,
            "advice_count": 0,
            "banned": False,
            "last_confession_ts": 0.0,
            "created_at": _now(),
        }
        await self.users.insert_one(doc)
        return doc

    async def set_banned(self, user_id: int, banned: bool) -> None:
        await self.ensure_user(user_id)
        await self.users.update_one({"user_id": user_id}, {"$set": {"banned": banned}})

    async def is_banned(self, user_id: int) -> bool:
        doc = await self.users.find_one({"user_id": user_id}, {"banned": 1})
        return bool(doc and doc.get("banned"))

    async def remaining_cooldown(self, user_id: int, window: int) -> int:
        """Return seconds left on cooldown (0 if user can confess now)."""
        doc = await self.users.find_one({"user_id": user_id}, {"last_confession_ts": 1})
        last = float((doc or {}).get("last_confession_ts") or 0)
        elapsed = time.time() - last
        remaining = int(window - elapsed)
        return max(remaining, 0)

    async def mark_confessed(self, user_id: int) -> None:
        await self.ensure_user(user_id)
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_confession_ts": time.time()},
             "$inc": {"confession_count": 1}},
        )

    # ----- confessions -------------------------------------------------------
    async def find_duplicate(self, guild_id: int, content_hash: str) -> dict[str, Any] | None:
        return await self.confessions.find_one(
            {"guild_id": guild_id, "content_hash": content_hash}
        )

    async def create_confession(
        self,
        *,
        guild_id: int,
        author_id: int,
        content: str,
        content_hash: str,
        category: str,
        status: str,
    ) -> dict[str, Any]:
        confession_id = await self.next_sequence(f"confession:{guild_id}")
        doc = {
            "confession_id": confession_id,
            "guild_id": guild_id,
            "author_id": author_id,    # PRIVATE — never sent to non-admins
            "content": content,
            "content_hash": content_hash,
            "category": category,
            "status": status,          # "pending" | "posted" | "rejected" | "deleted"
            "message_id": None,
            "thread_id": None,
            "channel_id": None,
            "reactions": {},
            "created_at": _now(),
        }
        await self.confessions.insert_one(doc)
        return doc

    async def attach_message(
        self,
        confession_id: int,
        *,
        channel_id: int,
        message_id: int,
        thread_id: int | None,
    ) -> None:
        await self.confessions.update_one(
            {"confession_id": confession_id},
            {"$set": {
                "channel_id": channel_id,
                "message_id": message_id,
                "thread_id": thread_id,
                "status": "posted",
            }},
        )

    async def set_status(self, confession_id: int, status: str) -> None:
        await self.confessions.update_one(
            {"confession_id": confession_id}, {"$set": {"status": status}}
        )

    async def get_confession(self, confession_id: int) -> dict[str, Any] | None:
        return await self.confessions.find_one({"confession_id": confession_id})

    async def get_confession_by_message(self, message_id: int) -> dict[str, Any] | None:
        return await self.confessions.find_one({"message_id": message_id})

    async def increment_reaction(self, confession_id: int, emoji: str, delta: int = 1) -> None:
        await self.confessions.update_one(
            {"confession_id": confession_id},
            {"$inc": {f"reactions.{emoji}": delta}},
        )

    # ----- advice ------------------------------------------------------------
    async def add_advice(self, confession_id: int, advisor_id: int, content: str) -> int:
        advice_id = await self.next_sequence(f"advice:{confession_id}")
        await self.advice.insert_one({
            "advice_id": advice_id,
            "confession_id": confession_id,
            "advisor_id": advisor_id,   # PRIVATE
            "content": content,
            "created_at": _now(),
        })
        await self.users.update_one(
            {"user_id": advisor_id},
            {"$inc": {"advice_count": 1}},
            upsert=True,
        )
        return advice_id

    # ----- reports -----------------------------------------------------------
    async def add_report(self, confession_id: int, reporter_id: int, reason: str) -> None:
        await self.reports.insert_one({
            "confession_id": confession_id,
            "reporter_id": reporter_id,
            "reason": reason,
            "created_at": _now(),
        })

    # ----- stats -------------------------------------------------------------
    async def stats_for_guild(self, guild_id: int) -> dict[str, Any]:
        total_confessions = await self.confessions.count_documents(
            {"guild_id": guild_id, "status": "posted"}
        )
        confession_ids = [
            c["confession_id"]
            async for c in self.confessions.find(
                {"guild_id": guild_id}, {"confession_id": 1}
            )
        ]
        total_advice = (
            await self.advice.count_documents({"confession_id": {"$in": confession_ids}})
            if confession_ids else 0
        )

        # Most reacted confession
        most_reacted = None
        async for c in self.confessions.find(
            {"guild_id": guild_id, "status": "posted"}
        ):
            total = sum(int(v) for v in (c.get("reactions") or {}).values())
            if most_reacted is None or total > most_reacted[1]:
                most_reacted = (c["confession_id"], total)

        return {
            "total_confessions": total_confessions,
            "total_advice": total_advice,
            "most_reacted": most_reacted,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)
