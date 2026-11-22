"""LLM response cache. MongoDB-backed when configured, in-memory otherwise."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from motor.motor_asyncio import AsyncIOMotorCollection

from app.config import Settings
from app.db import get_database


class Cache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: dict[str, Any]) -> None: ...


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value


class MongoCache:
    """Stores entries in the `llm_cache` collection, keyed by input hash."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection
        self._indexed = False

    async def _ensure_index(self) -> None:
        if not self._indexed:
            await self._col.create_index("key", unique=True)
            self._indexed = True

    async def get(self, key: str) -> dict[str, Any] | None:
        await self._ensure_index()
        doc = await self._col.find_one({"key": key})
        return doc["response"] if doc else None

    async def set(self, key: str, value: dict[str, Any]) -> None:
        await self._ensure_index()
        await self._col.update_one(
            {"key": key},
            {"$set": {"response": value, "created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )


def build_cache(settings: Settings) -> Cache:
    db = get_database(settings)
    return MongoCache(db["llm_cache"]) if db is not None else MemoryCache()
