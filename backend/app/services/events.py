"""Append-only event log. The org dashboard's rollups (M10) are built from it. Events carry ids and tags, never
names, phone numbers or free text."""
from __future__ import annotations

import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import timeutil


async def record(
    db: AsyncIOMotorDatabase,
    type_: str,
    actor: str,
    *,
    ref: str | None = None,
    block: str | None = None,
    district: str | None = None,
    skill_tags: list[str] | None = None,
) -> None:
    await db["events"].insert_one(
        {
            "_id": uuid.uuid4().hex,
            "type": type_,
            "actor": actor,
            "ref": ref,
            "block": block,
            "district": district,
            "skill_tags": skill_tags or [],
            "ts": timeutil.utcnow(),
        }
    )
