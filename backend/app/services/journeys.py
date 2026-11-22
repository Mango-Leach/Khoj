"""The journey state machine (CLAUDE.md section 6).

A journey is created when a learner picks a path (`path_selected`). Every change of state goes through `move`,
which checks the move is allowed and applies it with one conditional update, so two requests racing for the same
journey cannot both win.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app import timeutil

# A declined or lapsed mentor request returns the learner to `path_selected`: the career is already chosen, so they
# only need another mentor. (The source spec says `assessed`, which assumed the journey did not exist yet.)
TRANSITIONS: dict[str, frozenset[str]] = {
    "path_selected": frozenset({"mentor_pending", "abandoned"}),
    "mentor_pending": frozenset({"in_progress", "path_selected", "abandoned"}),
    "in_progress": frozenset({"completed", "stalled", "abandoned"}),
    "stalled": frozenset({"in_progress", "abandoned"}),
    "completed": frozenset({"opportunities_open"}),
    "opportunities_open": frozenset({"enrolled", "in_progress", "abandoned"}),
    "enrolled": frozenset(),
    "abandoned": frozenset(),
}
TERMINAL = frozenset({"enrolled", "abandoned"})
# These hold a place with a mentor, so they count against the mentor's capacity.
HOLDS_MENTOR_SLOT = ("mentor_pending", "in_progress", "stalled")


def can_move(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def sources_for(target: str) -> list[str]:
    """Every state a journey may be in right before it moves to `target`."""
    return [state for state, nxt in TRANSITIONS.items() if target in nxt]


async def move(db: AsyncIOMotorDatabase, journey_id: str, target: str, *, expect: str | None = None, **fields: Any) -> dict[str, Any] | None:
    """Move a journey to `target`. Returns the updated journey, or None if it was not in an allowed state.

    `expect` narrows the starting state further (for example, only `mentor_pending` may become `in_progress`).
    """
    allowed = [expect] if expect else sources_for(target)
    allowed = [s for s in allowed if can_move(s, target)]
    if not allowed:
        return None
    return await db["journeys"].find_one_and_update(
        {"_id": journey_id, "state": {"$in": allowed}},
        {"$set": {"state": target, "updated_at": timeutil.utcnow(), **fields}},
        return_document=ReturnDocument.AFTER,
    )


async def active_counts(db: AsyncIOMotorDatabase, teacher_user_ids: list[str]) -> dict[str, int]:
    """How many learners each mentor currently holds a place for (pending requests count, so a place is never promised twice)."""
    if not teacher_user_ids:
        return {}
    counts = {tid: 0 for tid in teacher_user_ids}
    pipeline = [
        {"$match": {"teacher_id": {"$in": teacher_user_ids}, "state": {"$in": list(HOLDS_MENTOR_SLOT)}}},
        {"$group": {"_id": "$teacher_id", "n": {"$sum": 1}}},
    ]
    async for row in db["journeys"].aggregate(pipeline):
        counts[row["_id"]] = row["n"]
    return counts
