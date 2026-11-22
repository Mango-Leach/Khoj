"""Choosing a mentor: three candidates, a request, and the mentor's answer within 48 hours.

A request holds one place with the mentor straight away (it counts against their capacity), so two learners cannot
be promised the same last place. A request nobody answers within 48 hours lapses and the learner may choose again.
Everything is read through the caller's own user id in this layer.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app import timeutil
from app.errors import ApiError
from app.services import assessments, calls, catalog, events, journeys, matching, notifications
from app.services.profiles import capacity_limit

REQUEST_WINDOW = timedelta(hours=48)
RECENT_DECIDED = 10


def _skill_names() -> dict[str, dict[str, str]]:
    return {s["id"]: s["name"] for s in catalog.skills()}


# ---------------------------------------------------------------------------
# Lapsed requests
# ---------------------------------------------------------------------------


async def expire_stale(db: AsyncIOMotorDatabase) -> int:
    """Close requests nobody answered in time and give the learners back their choice. Safe to call often."""
    now = timeutil.utcnow()
    closed = 0
    async for m in db["matches"].find({"status": "pending", "expires_at": {"$lte": now}}):
        claimed = await db["matches"].find_one_and_update(
            {"_id": m["_id"], "status": "pending"}, {"$set": {"status": "expired", "decided_at": now}}, return_document=ReturnDocument.AFTER
        )
        if claimed is None:
            continue
        await journeys.move(db, m["journey_id"], "path_selected", expect="mentor_pending", teacher_id=None)
        await events.record(db, "mentor_request_expired", m["student_id"], ref=m["_id"])
        closed += 1
    return closed


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _candidate_view(teacher: dict[str, Any], career: dict[str, Any], result: dict[str, Any], student: dict[str, Any], student_language: str, free: int) -> dict[str, Any]:
    return {
        "teacher_id": teacher["_id"],  # the profile id; the account id is never sent to another user
        "name": teacher["name"],
        "roles": teacher["roles"],
        "languages": teacher["languages"],
        "district": teacher["district"],
        "block": teacher["block"],
        "tier": teacher["tier"],
        # the skill checks the mentor passed, by name: one check proves a bundle of skills, so a skill-by-skill list would claim too much
        "verified_in": calls.verified_areas(teacher, career),
        "speaks_your_language": student_language in teacher["languages"],
        "same_block": result["factors"]["place"] == 1.0,
        "same_district": result["factors"]["place"] >= 0.5,
        "free_places": free,
        "explain": {"score": result["score"], "factors": result["factors"]},
    }


def _request_view(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": m["_id"],
        "journey_id": m["journey_id"],
        "status": m["status"],
        "created_at": timeutil.ensure_aware(m["created_at"]),
        "expires_at": timeutil.ensure_aware(m["expires_at"]),
        "decided_at": timeutil.ensure_aware(m["decided_at"]) if m.get("decided_at") else None,
    }


async def _own_journey(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> dict[str, Any]:
    journey = await db["journeys"].find_one({"_id": journey_id, "student_id": user["_id"]})  # scoped to the caller here
    if journey is None:
        raise ApiError(404, "journey_not_found", "We could not find that journey.", "Go back and pick a path.")
    return journey


async def journey_view(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    """The learner's live journey with the state of the mentor choice."""
    await expire_stale(db)
    doc = await db["journeys"].find_one({"student_id": user["_id"], "state": {"$ne": "abandoned"}}, sort=[("created_at", -1)])
    if doc is None:
        raise ApiError(404, "no_journey", "You have not picked a path yet.", "Pick one from your paths.")
    out = assessments.journey_view(doc)
    mentor = None
    if doc.get("teacher_id") and doc["state"] in ("mentor_pending", "in_progress", "stalled"):
        t = await db["teacher_profiles"].find_one({"user_id": doc["teacher_id"]})
        if t:
            mentor = {"teacher_id": t["_id"], "name": t["name"], "roles": t["roles"], "languages": t["languages"], "district": t["district"], "block": t["block"], "tier": t["tier"]}
    latest = await db["matches"].find_one({"journey_id": doc["_id"]}, sort=[("created_at", -1)])
    return {**out, "mentor": mentor, "request": _request_view(latest) if latest else None}


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


async def _context(db: AsyncIOMotorDatabase, user: dict[str, Any], journey: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    career = catalog.career(journey["career_id"])
    student = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if career is None or student is None:
        raise ApiError(409, "profile_required", "Please finish your profile first.", "")
    return career, student, user.get("language", "en")


async def _eligible(
    db: AsyncIOMotorDatabase, career: dict[str, Any], student: dict[str, Any], language: str, exclude: set[str], only: str | None = None
) -> list[tuple[dict[str, Any], dict[str, Any], int]]:
    query: dict[str, Any] = {"tier": {"$gte": 1}}
    if only:
        query["_id"] = only
    teachers = [t async for t in db["teacher_profiles"].find(query) if t["_id"] not in exclude]
    counts = await journeys.active_counts(db, [t["user_id"] for t in teachers])
    out = []
    for t in teachers:
        limit = capacity_limit(t)
        free = limit - counts.get(t["user_id"], 0)
        result = matching.score(career, t, student, language, free, limit)
        if result is not None:
            out.append((t, result, free))
    return out


async def _turned_away(db: AsyncIOMotorDatabase, journey_id: str) -> set[str]:
    """Mentors who already declined (or let lapse) a request for this journey are not offered again."""
    return {m["teacher_profile_id"] async for m in db["matches"].find({"journey_id": journey_id, "status": {"$in": ["declined", "expired"]}})}


async def candidates(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> dict[str, Any]:
    await expire_stale(db)
    journey = await _own_journey(db, user, journey_id)
    if journey["state"] != "path_selected":
        raise ApiError(409, "mentor_already_chosen", "You already have a mentor request for this path.", "Open your mentor page to see it.")
    career, student, language = await _context(db, user, journey)
    found = await _eligible(db, career, student, language, await _turned_away(db, journey_id))
    free_by_id = {t["_id"]: free for t, _, free in found}
    ranked = matching.top_candidates([(t, r) for t, r, _ in found])
    return {
        "journey_id": journey_id,
        "career_id": journey["career_id"],
        "candidates": [_candidate_view(t, career, r, student, language, free_by_id[t["_id"]]) for t, r in ranked],
    }


# ---------------------------------------------------------------------------
# Request, cancel
# ---------------------------------------------------------------------------


async def request_mentor(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str, teacher_profile_id: str) -> dict[str, Any]:
    await expire_stale(db)
    journey = await _own_journey(db, user, journey_id)

    if journey["state"] == "mentor_pending":
        pending = await db["matches"].find_one({"journey_id": journey_id, "status": "pending"})
        if pending and pending["teacher_profile_id"] == teacher_profile_id:
            return _request_view(pending)  # the same request sent twice is one request
        raise ApiError(409, "request_pending", "You already asked a mentor.", "Wait for the answer, or cancel it first.")
    if journey["state"] != "path_selected":
        raise ApiError(409, "mentor_already_chosen", "This path already has a mentor.", "")

    career, student, language = await _context(db, user, journey)
    turned = await _turned_away(db, journey_id)
    if teacher_profile_id in turned:
        raise ApiError(409, "mentor_unavailable", "This mentor is not available for you.", "Pick another mentor.")
    found = await _eligible(db, career, student, language, turned, only=teacher_profile_id)
    if not found:
        raise ApiError(409, "mentor_unavailable", "This mentor cannot take a new learner right now.", "Pick another mentor.")
    teacher, result, _ = found[0]

    now = timeutil.utcnow()
    moved = await journeys.move(db, journey_id, "mentor_pending", expect="path_selected", teacher_id=teacher["user_id"])
    if moved is None:
        raise ApiError(409, "request_pending", "You already asked a mentor.", "Wait for the answer, or cancel it first.")
    match = {
        "_id": uuid.uuid4().hex,
        "journey_id": journey_id,
        "student_id": user["_id"],
        "teacher_id": teacher["user_id"],
        "teacher_profile_id": teacher["_id"],
        "career_id": journey["career_id"],
        "status": "pending",
        "score": result["score"],
        "factors": result["factors"],
        "created_at": now,
        "expires_at": now + REQUEST_WINDOW,
        "decided_at": None,
    }
    await db["matches"].insert_one(match)
    await events.record(db, "mentor_requested", user["_id"], ref=match["_id"], block=student["block"], district=student["district"], skill_tags=result["skills"])
    await notifications.notify(db, teacher["user_id"], "mentor_request", "/t/requests", dedupe_key=f"mentor_request:{match['_id']}")
    return _request_view(match)


async def cancel_request(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> dict[str, Any]:
    await expire_stale(db)
    await _own_journey(db, user, journey_id)
    now = timeutil.utcnow()
    claimed = await db["matches"].find_one_and_update(
        {"journey_id": journey_id, "student_id": user["_id"], "status": "pending"},
        {"$set": {"status": "cancelled", "decided_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if claimed is None:
        raise ApiError(409, "nothing_to_cancel", "There is no waiting request to cancel.", "")
    await journeys.move(db, journey_id, "path_selected", expect="mentor_pending", teacher_id=None)
    return _request_view(claimed)


# ---------------------------------------------------------------------------
# The mentor's side
# ---------------------------------------------------------------------------


async def _my_teacher(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    t = await db["teacher_profiles"].find_one({"user_id": user["_id"]})
    if t is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")
    return t


async def _student_card(db: AsyncIOMotorDatabase, match: dict[str, Any]) -> dict[str, Any]:
    """What a mentor sees about a learner: enough to decide, nothing about phone or exact address."""
    s = await db["student_profiles"].find_one({"user_id": match["student_id"]}) or {}
    u = await db["users"].find_one({"_id": match["student_id"]}, {"language": 1}) or {}
    career = catalog.career(match["career_id"])
    journey = await db["journeys"].find_one({"_id": match["journey_id"]}) or {}
    assessment = await db["assessments"].find_one({"_id": journey.get("assessment_id")}) if journey.get("assessment_id") else None
    names = _skill_names()
    skills = [{"id": k, "name": names.get(k, {"en": k})} for k in (assessment or {}).get("based_on", {}).get("skills", [])]
    age = s.get("age")
    return {
        "name": s.get("name", ""),
        "age_band": s.get("age_band"),
        "grade": s.get("grade"),
        "district": s.get("district"),
        "block": s.get("block"),
        "language": u.get("language", "en"),
        "guardian_consent": bool((s.get("guardian_consent") or {}).get("given")),
        "career": assessments.career_card(career) if career else {"career_id": match["career_id"]},
        "skills": skills,
        # a plain flag so the mentor plans theory and a training board only for a young learner on a hazardous path
        "theory_only": bool(career and career["safety"]["under18_theory_only"] and age is not None and age < 18),
    }


async def teacher_requests(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    await expire_stale(db)
    teacher = await _my_teacher(db, user)
    pending = [m async for m in db["matches"].find({"teacher_id": user["_id"], "status": "pending"}).sort("created_at", 1)]
    recent = [m async for m in db["matches"].find({"teacher_id": user["_id"], "status": {"$ne": "pending"}}).sort("decided_at", -1).limit(RECENT_DECIDED)]
    counts = await journeys.active_counts(db, [user["_id"]])
    limit = capacity_limit(teacher)
    return {
        "capacity": {"limit": limit, "free": max(0, limit - counts.get(user["_id"], 0))},
        "pending": [{**_request_view(m), "student": await _student_card(db, m)} for m in pending],
        "recent": [{**_request_view(m), "student": await _student_card(db, m)} for m in recent],
    }


async def decide(db: AsyncIOMotorDatabase, user: dict[str, Any], match_id: str, accept: bool) -> dict[str, Any]:
    await expire_stale(db)
    match = await db["matches"].find_one({"_id": match_id, "teacher_id": user["_id"]})  # scoped to the caller here
    if match is None:
        raise ApiError(404, "request_not_found", "We could not find that request.", "")
    if match["status"] == "expired":
        raise ApiError(409, "request_expired", "This request ran out of time.", "The learner can choose another mentor.")
    if match["status"] != "pending":
        raise ApiError(409, "already_decided", "This request has already been answered.", "")

    now = timeutil.utcnow()
    status = "accepted" if accept else "declined"
    claimed = await db["matches"].find_one_and_update(
        {"_id": match_id, "status": "pending"}, {"$set": {"status": status, "decided_at": now}}, return_document=ReturnDocument.AFTER
    )
    if claimed is None:
        raise ApiError(409, "already_decided", "This request has already been answered.", "")

    if accept:
        moved = await journeys.move(db, match["journey_id"], "in_progress", expect="mentor_pending", mentor_since=now)
        if moved is None:  # the learner changed their mind at the same moment
            await db["matches"].update_one({"_id": match_id}, {"$set": {"status": "cancelled"}})
            raise ApiError(409, "request_cancelled", "The learner has cancelled this request.", "")
    else:
        await journeys.move(db, match["journey_id"], "path_selected", expect="mentor_pending", teacher_id=None)
    await events.record(db, f"mentor_request_{status}", user["_id"], ref=match_id)
    await notifications.notify(
        db,
        match["student_id"],
        "mentor_accepted" if accept else "mentor_declined",
        "/assignments" if accept else "/mentor",
        dedupe_key=f"mentor_{status}:{match_id}",
    )
    return {**_request_view(claimed), "student": await _student_card(db, claimed)}


async def my_students(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> list[dict[str, Any]]:
    await _my_teacher(db, user)
    out = []
    async for j in db["journeys"].find({"teacher_id": user["_id"], "state": {"$in": ["in_progress", "stalled"]}}).sort("mentor_since", 1):
        match = await db["matches"].find_one({"journey_id": j["_id"], "status": "accepted"})
        if match is None:
            continue
        out.append(
            {
                "journey_id": j["_id"],
                "state": j["state"],
                "since": timeutil.ensure_aware(j["mentor_since"]) if j.get("mentor_since") else None,
                "student": await _student_card(db, match),
            }
        )
    return out
