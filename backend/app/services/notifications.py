"""The in-app inbox (CLAUDE.md section 14).

Every notification is stored as a kind and a few plain parameters, never as finished text. The app turns the kind
into a short, neutral sentence in the reader's own language, so a message that shows on a shared phone says
"You have something new in KHOJ" and never the learner's name or a private detail. Every message carries a deep link.

The spec's push rules (quiet hours from 9 pm to 7 am, at most two a day) apply to web push, which is not built yet;
the inbox itself keeps everything. A message can carry a `dedupe_key`: sending the same key twice stores it once, so
a retried request never fills the inbox with copies.
"""
from __future__ import annotations

import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app import timeutil
from app.errors import ApiError

# What may be sent. The app has one sentence for each, in every language.
KINDS = frozenset(
    {
        "mentor_request",  # to a mentor: a learner asked you
        "mentor_accepted",  # to a learner
        "mentor_declined",  # to a learner
        "work_sent",  # to a mentor: new work is waiting
        "review_ready",  # to a learner: feedback is ready
        "path_complete",  # to a learner: the practice path is finished, opportunities are open
        "help_apply",  # to a mentor: a learner wants help applying
        "mentor_helped",  # to a learner: the mentor marked their help as done
        "call_booked",  # to a mentor: a learner booked a career call
        "call_cancelled",  # to a mentor or a learner: a booked career call was cancelled
        "connect_request",  # to an adult learner: another adult learner asked to connect
        "connect_accepted",  # to an adult learner: your connection request was accepted
    }
)
LIST_LIMIT = 50
MAX_PARAMS = 6


def _clean_params(params: dict[str, Any] | None) -> dict[str, str]:
    """Only short plain strings are kept, so a notification can never carry a name, a number or free text by accident."""
    out: dict[str, str] = {}
    for key, value in (params or {}).items():
        if isinstance(value, (str, int)) and len(out) < MAX_PARAMS:
            out[str(key)[:30]] = str(value)[:60]
    return out


async def notify(
    db: AsyncIOMotorDatabase,
    user_id: str,
    kind: str,
    link: str,
    *,
    params: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Store one notification. Returns False when the same `dedupe_key` was already sent."""
    if kind not in KINDS:
        raise ValueError(f"unknown notification kind: {kind}")
    doc = {
        "_id": f"{user_id}:{dedupe_key}" if dedupe_key else uuid.uuid4().hex,
        "user_id": user_id,
        "kind": kind,
        "params": _clean_params(params),
        "link": link,
        "read_at": None,
        "created_at": timeutil.utcnow(),
    }
    try:
        await db["notifications"].insert_one(doc)
    except DuplicateKeyError:
        return False
    return True


def _view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "kind": doc["kind"],
        "params": doc.get("params", {}),
        "link": doc["link"],
        "read": doc.get("read_at") is not None,
        "created_at": timeutil.ensure_aware(doc["created_at"]),
    }


async def unread_count(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> int:
    return await db["notifications"].count_documents({"user_id": user["_id"], "read_at": None})


async def list_for(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    items = [_view(d) async for d in db["notifications"].find({"user_id": user["_id"]}).sort("created_at", -1).limit(LIST_LIMIT)]
    return {"items": items, "unread": await unread_count(db, user)}


async def mark_read(db: AsyncIOMotorDatabase, user: dict[str, Any], notification_id: str) -> dict[str, Any]:
    now = timeutil.utcnow()
    # scoped to the caller here: another person's id simply is not found
    doc = await db["notifications"].find_one({"_id": notification_id, "user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "notification_not_found", "We could not find that message.", "")
    if doc.get("read_at") is None:
        await db["notifications"].update_one({"_id": notification_id, "read_at": None}, {"$set": {"read_at": now}})
        doc["read_at"] = now
    return {"notification": _view(doc), "unread": await unread_count(db, user)}


async def mark_all_read(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    await db["notifications"].update_many({"user_id": user["_id"], "read_at": None}, {"$set": {"read_at": timeutil.utcnow()}})
    return {"unread": 0}
