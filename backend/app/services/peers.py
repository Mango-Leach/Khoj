"""Connect: adult learners with similar goals can find each other, and then talk however they like outside KHOJ.

KHOJ never carries the conversation. It only introduces two people who both agreed. Rules that keep it as safe as an
open introduction can be:

* Adults only. Every call is checked against the learner's age in this layer, and learners under 18 see nothing.
  The age is what the learner entered, so this is not proof of age.
* A card is hidden until the learner switches it on. It shows a first name, the state, the path they picked and the
  skills from the controlled list. No photo, no surname, no school, no district or block, no free text, no contact.
* Suggestions only: people on the same path or with a skill in common. There is no search by name and no list of everyone.
* Contact is exchanged only after one person asks and the other accepts, and both must have switched their card on.
  The contact is the one thing each person typed in for this purpose (a phone number or an https link).
* A learner can decline, remove a connection, block, or report. A blocked person never appears again, either way round.
* At most 5 new requests a day, and a person who declined or was removed cannot be asked again.
* Everything is read through the caller's own user id in this layer.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import timeutil
from app.errors import ApiError
from app.models.peers import MyCardIn, ReportIn
from app.services import catalog, events, notifications, opportunities

ADULT_AGE = 18
REQUESTS_PER_DAY = 5
SUGGESTIONS = 12
SCAN_LIMIT = 300  # how many visible cards are read to pick suggestions


def _pair(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


async def _learner(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    s = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if s is None:
        raise ApiError(409, "profile_required", "Please finish your profile first.", "")
    return s


def _adult(student: dict[str, Any]) -> None:
    if student["age"] < ADULT_AGE:
        raise ApiError(403, "peer_underage", "Connecting opens at 18.", "")


async def _my_skills(db: AsyncIOMotorDatabase, user_id: str) -> list[str]:
    """The skills the learner confirmed (controlled list only). Free text from the intake is never shown to anyone."""
    doc = await db["intake_sessions"].find_one({"user_id": user_id, "status": "done"}, sort=[("completed_at", -1)])
    return list((doc or {}).get("extracted", {}).get("skills", []))


async def _current_career(db: AsyncIOMotorDatabase, user_id: str) -> str | None:
    j = await db["journeys"].find_one({"student_id": user_id, "state": {"$ne": "abandoned"}}, sort=[("created_at", -1)])
    return j["career_id"] if j else None


def _skill_names(ids: list[str]) -> list[dict[str, Any]]:
    names = {s["id"]: s["name"] for s in catalog.skills()}
    return [{"id": i, "name": names[i]} for i in ids if i in names]


async def _card(db: AsyncIOMotorDatabase, profile: dict[str, Any], mine: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """What another learner sees. The account id never leaves this layer; the card id is its own random id."""
    student = await db["student_profiles"].find_one({"user_id": profile["user_id"]})
    if student is None or student["age"] < ADULT_AGE:
        return None
    career_id = await _current_career(db, profile["user_id"])
    career = catalog.career(career_id) if career_id else None
    skills = await _my_skills(db, profile["user_id"])
    shared: list[str] = []
    if mine is not None:
        shared = [s for s in skills if s in mine["skills"]]
    return {
        "card_id": profile["_id"],
        "first_name": (student.get("name") or "").split(" ")[0],
        "state": student.get("state"),
        "career_id": career_id,
        "career_name": career["name"] if career else None,
        "skills": _skill_names(skills),
        "shared_skills": shared,
        "same_path": bool(mine and career_id and career_id == mine["career_id"]),
    }


async def _blocked_with(db: AsyncIOMotorDatabase, user_id: str) -> set[str]:
    out: set[str] = set()
    async for b in db["peer_blocks"].find({"$or": [{"by": user_id}, {"target": user_id}]}):
        out.add(b["target"] if b["by"] == user_id else b["by"])
    return out


# ---------------------------------------------------------------------------
# The learner's own card
# ---------------------------------------------------------------------------


async def _my_profile(db: AsyncIOMotorDatabase, user_id: str) -> dict[str, Any] | None:
    return await db["connect_profiles"].find_one({"user_id": user_id})


def _own_view(p: dict[str, Any] | None) -> dict[str, Any]:
    if p is None:
        return {"visible": False, "reach_kind": "phone", "reach": ""}
    return {"visible": bool(p["visible"]), "reach_kind": p["reach_kind"], "reach": p["reach"]}


async def set_card(db: AsyncIOMotorDatabase, user: dict[str, Any], body: MyCardIn) -> dict[str, Any]:
    student = await _learner(db, user)
    _adult(student)
    now = timeutil.utcnow()
    existing = await _my_profile(db, user["_id"])
    if not body.visible:
        if existing is not None:
            await db["connect_profiles"].update_one({"_id": existing["_id"]}, {"$set": {"visible": False, "updated_at": now}})
        return await overview(db, user)
    if await _current_career(db, user["_id"]) is None:
        raise ApiError(409, "no_path", "Pick a path first.", "Choose a path first.")
    if not body.agreed:
        raise ApiError(409, "peer_agree_needed", "Please tick that you understand.", "")
    try:
        reach = body.checked_reach()
    except ValueError:
        raise ApiError(422, "contact_invalid", "Check the link or phone number.", "A link starts with https:// and a phone number has 10 digits.")
    doc = {"visible": True, "reach_kind": body.reach_kind, "reach": reach, "agreed_at": now, "updated_at": now}
    if existing is None:
        await db["connect_profiles"].insert_one({"_id": uuid.uuid4().hex, "user_id": user["_id"], "created_at": now, **doc})
    else:
        await db["connect_profiles"].update_one({"_id": existing["_id"]}, {"$set": doc})
    return await overview(db, user)


# ---------------------------------------------------------------------------
# What the learner sees
# ---------------------------------------------------------------------------


async def overview(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    student = await _learner(db, user)
    if student["age"] < ADULT_AGE:
        return {"eligible": False, "opens_at": ADULT_AGE}
    career_id = await _current_career(db, user["_id"])
    if career_id is None:
        raise ApiError(409, "no_path", "Pick a path to connect with others.", "Choose a path first.")
    career = catalog.career(career_id)
    me = await _my_profile(db, user["_id"])
    now = timeutil.utcnow()
    mine = {"career_id": career_id, "skills": await _my_skills(db, user["_id"])}
    blocked = await _blocked_with(db, user["_id"])

    rows = [c async for c in db["connections"].find({"$or": [{"requester": user["_id"]}, {"recipient": user["_id"]}]})]
    seen: set[str] = {user["_id"], *blocked}
    for r in rows:
        seen.add(r["recipient"] if r["requester"] == user["_id"] else r["requester"])

    async def other_card(r: dict[str, Any], need_visible: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        other_id = r["recipient"] if r["requester"] == user["_id"] else r["requester"]
        if other_id in blocked:
            return None, None
        p = await _my_profile(db, other_id)
        if p is None or (need_visible and not p["visible"]):
            return None, None
        return await _card(db, p, mine), p

    incoming, outgoing, connections = [], [], []
    for r in rows:
        if r["status"] == "pending" and r["recipient"] == user["_id"]:
            card, _ = await other_card(r, True)
            if card:
                incoming.append({"id": r["_id"], "card": card})
        elif r["status"] == "pending":
            card, _ = await other_card(r, False)
            if card:
                outgoing.append({"id": r["_id"], "card": card})
        elif r["status"] == "accepted":
            card, p = await other_card(r, False)
            if card and p:
                # contact is shown only while the other person's card is still on
                connections.append({"id": r["_id"], "card": card, "reach_kind": p["reach_kind"] if p["visible"] else None, "reach": p["reach"] if p["visible"] else None})

    suggestions: list[tuple[int, dict[str, Any]]] = []
    if me is not None and me["visible"]:
        async for p in db["connect_profiles"].find({"visible": True, "user_id": {"$nin": list(seen)}}).limit(SCAN_LIMIT):
            card = await _card(db, p, mine)
            if card is None:
                continue
            score = (10 if card["same_path"] else 0) + len(card["shared_skills"])
            if score > 0:
                suggestions.append((score, card))
        suggestions.sort(key=lambda x: (-x[0], x[1]["card_id"]))

    sent_today = await db["connections"].count_documents({"requester": user["_id"], "created_at": {"$gte": now - timedelta(days=1)}})
    return {
        "eligible": True,
        "career_id": career_id,
        "career_name": career["name"] if career else {"en": career_id},
        "me": _own_view(me),
        "my_skills": _skill_names(mine["skills"]),
        "suggestions": [c for _, c in suggestions[:SUGGESTIONS]],
        "incoming": incoming,
        "outgoing": outgoing,
        "connections": connections,
        "requests_left": max(0, REQUESTS_PER_DAY - sent_today),
        "limits": {"per_day": REQUESTS_PER_DAY},
    }


# ---------------------------------------------------------------------------
# Asking, answering, and stopping
# ---------------------------------------------------------------------------


async def _need_my_card(db: AsyncIOMotorDatabase, user_id: str) -> dict[str, Any]:
    me = await _my_profile(db, user_id)
    if me is None or not me["visible"]:
        raise ApiError(409, "peer_need_card", "Switch on your card first.", "Others can connect only with people who share a card.")
    return me


async def _target(db: AsyncIOMotorDatabase, user_id: str, card_id: str, need_visible: bool = True) -> dict[str, Any]:
    p = await db["connect_profiles"].find_one({"_id": card_id})
    if p is None or p["user_id"] == user_id or (need_visible and not p["visible"]):
        raise ApiError(404, "peer_not_found", "We could not find this person.", "")
    if p["user_id"] in await _blocked_with(db, user_id):
        raise ApiError(404, "peer_not_found", "We could not find this person.", "")  # a block is never revealed
    other = await db["student_profiles"].find_one({"user_id": p["user_id"]})
    if other is None or other["age"] < ADULT_AGE:
        raise ApiError(404, "peer_not_found", "We could not find this person.", "")
    return p


async def _student_for_events(db: AsyncIOMotorDatabase, user_id: str) -> dict[str, Any]:
    return await db["student_profiles"].find_one({"user_id": user_id}) or {}


async def request(db: AsyncIOMotorDatabase, user: dict[str, Any], card_id: str) -> dict[str, Any]:
    student = await _learner(db, user)
    _adult(student)
    await _need_my_card(db, user["_id"])
    target = await _target(db, user["_id"], card_id)
    other_id = target["user_id"]
    now = timeutil.utcnow()
    existing = await db["connections"].find_one({"pair": _pair(user["_id"], other_id)})
    if existing is not None:
        if existing["status"] == "pending" and existing["requester"] == other_id:
            return await _answer(db, user, existing["_id"], True)  # they had already asked: asking back is accepting
        if existing["status"] in ("pending", "accepted"):
            raise ApiError(409, "peer_already", "You are already connected or waiting for an answer.", "")
        raise ApiError(409, "peer_unavailable", "This person is not available.", "")
    sent_today = await db["connections"].count_documents({"requester": user["_id"], "created_at": {"$gte": now - timedelta(days=1)}})
    if sent_today >= REQUESTS_PER_DAY:
        raise ApiError(429, "peer_limit", "You have sent the most requests for today.", "Try again tomorrow.")
    doc = {"_id": uuid.uuid4().hex, "pair": _pair(user["_id"], other_id), "requester": user["_id"], "recipient": other_id, "status": "pending", "created_at": now, "responded_at": None}
    try:
        await db["connections"].insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(409, "peer_already", "You are already connected or waiting for an answer.", "")
    await events.record(db, "connect_requested", user["_id"], ref=doc["_id"], block=student.get("block"), district=student.get("district"))
    await notifications.notify(db, other_id, "connect_request", "/connect")
    return {"id": doc["_id"], "status": "pending"}


async def _answer(db: AsyncIOMotorDatabase, user: dict[str, Any], request_id: str, accept: bool) -> dict[str, Any]:
    student = await _learner(db, user)
    _adult(student)
    row = await db["connections"].find_one({"_id": request_id, "recipient": user["_id"]})  # scoped to the caller here
    if row is None:
        raise ApiError(404, "peer_not_found", "We could not find this request.", "")
    if row["status"] != "pending":
        return {"id": request_id, "status": row["status"]}  # answering twice keeps the first answer
    if accept:
        await _need_my_card(db, user["_id"])
        if row["requester"] in await _blocked_with(db, user["_id"]):
            raise ApiError(404, "peer_not_found", "We could not find this request.", "")
    now = timeutil.utcnow()
    status = "accepted" if accept else "declined"
    claimed = await db["connections"].find_one_and_update(
        {"_id": request_id, "recipient": user["_id"], "status": "pending"}, {"$set": {"status": status, "responded_at": now}}, return_document=ReturnDocument.AFTER
    )
    if claimed is None:
        fresh = await db["connections"].find_one({"_id": request_id}) or row
        return {"id": request_id, "status": fresh["status"]}
    if accept:
        await events.record(db, "connect_accepted", user["_id"], ref=request_id, block=student.get("block"), district=student.get("district"))
        await notifications.notify(db, row["requester"], "connect_accepted", "/connect")
    return {"id": request_id, "status": status}


async def accept(db: AsyncIOMotorDatabase, user: dict[str, Any], request_id: str) -> dict[str, Any]:
    return await _answer(db, user, request_id, True)


async def decline(db: AsyncIOMotorDatabase, user: dict[str, Any], request_id: str) -> dict[str, Any]:
    return await _answer(db, user, request_id, False)


async def cancel(db: AsyncIOMotorDatabase, user: dict[str, Any], request_id: str) -> dict[str, Any]:
    """The person who asked takes the request back. It cannot be re-sent, so asking again is not a way to nag."""
    row = await db["connections"].find_one({"_id": request_id, "requester": user["_id"]})  # scoped to the caller here
    if row is None:
        raise ApiError(404, "peer_not_found", "We could not find this request.", "")
    if row["status"] == "pending":
        await db["connections"].update_one({"_id": request_id, "status": "pending"}, {"$set": {"status": "cancelled", "responded_at": timeutil.utcnow()}})
        return {"id": request_id, "status": "cancelled"}
    return {"id": request_id, "status": row["status"]}


async def remove(db: AsyncIOMotorDatabase, user: dict[str, Any], connection_id: str) -> dict[str, Any]:
    """Either person can end a connection. The other person is not told, and the pair cannot be asked again."""
    row = await db["connections"].find_one({"_id": connection_id, "$or": [{"requester": user["_id"]}, {"recipient": user["_id"]}]})
    if row is None:
        raise ApiError(404, "peer_not_found", "We could not find this connection.", "")
    if row["status"] == "accepted":
        await db["connections"].update_one({"_id": connection_id, "status": "accepted"}, {"$set": {"status": "removed", "responded_at": timeutil.utcnow()}})
        return {"id": connection_id, "status": "removed"}
    return {"id": connection_id, "status": row["status"]}


async def block(db: AsyncIOMotorDatabase, user: dict[str, Any], card_id: str) -> dict[str, Any]:
    student = await _learner(db, user)
    _adult(student)
    p = await db["connect_profiles"].find_one({"_id": card_id})
    if p is None or p["user_id"] == user["_id"]:
        raise ApiError(404, "peer_not_found", "We could not find this person.", "")
    now = timeutil.utcnow()
    await db["peer_blocks"].update_one({"by": user["_id"], "target": p["user_id"]}, {"$setOnInsert": {"_id": uuid.uuid4().hex, "created_at": now}}, upsert=True)
    # whatever stood between them is closed, and stays closed
    await db["connections"].update_many({"pair": _pair(user["_id"], p["user_id"]), "status": {"$in": ["pending", "accepted"]}}, {"$set": {"status": "blocked", "responded_at": now}})
    return {"blocked": True}


async def report(db: AsyncIOMotorDatabase, user: dict[str, Any], card_id: str, body: ReportIn) -> dict[str, Any]:
    """A report also blocks. It is recorded for the team; there is no review screen yet, so nothing is promised about an answer."""
    out = await block(db, user, card_id)
    p = await db["connect_profiles"].find_one({"_id": card_id})
    await db["peer_reports"].insert_one({"_id": uuid.uuid4().hex, "by": user["_id"], "target": p["user_id"], "reason": body.reason, "created_at": timeutil.utcnow()})
    await events.record(db, "connect_reported", user["_id"], ref=card_id)
    return {**out, "reported": True}
