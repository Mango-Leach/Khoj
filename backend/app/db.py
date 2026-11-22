"""MongoDB access. Everything degrades cleanly when no URI is configured."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings, get_settings

_client: AsyncIOMotorClient | None = None


def get_client(settings: Settings | None = None) -> AsyncIOMotorClient | None:
    """Return the shared client, or None when MONGODB_URI is empty."""
    global _client
    settings = settings or get_settings()
    if not settings.mongodb_uri:
        return None
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=2000, tz_aware=True)
    return _client


def get_database(settings: Settings | None = None) -> AsyncIOMotorDatabase | None:
    settings = settings or get_settings()
    client = get_client(settings)
    return client[settings.db_name] if client is not None else None


async def ping(settings: Settings | None = None) -> tuple[bool, str]:
    """Return (ok, detail). Never raises."""
    settings = settings or get_settings()
    client = get_client(settings)
    if client is None:
        return False, "not_configured"
    try:
        await client.admin.command("ping")
        return True, "ok"
    except Exception as exc:  # network, auth, DNS, allow-list: all just "unreachable" here
        return False, f"unreachable: {type(exc).__name__}"


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
