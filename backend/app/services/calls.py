"""A day in the life: a 30 or 45 minute call between a learner and someone who is verified in the skill.

KHOJ only handles the booking. The call happens on a video link or a phone call outside the app, so nothing is
recorded or streamed here. Rules that keep it honest and safe:

* A host is a mentor who has switched "offer career calls" on, is at tier 1 or above, and whose skill check and proof
  are approved for a skill the career needs. The label says "skill verified in ...", never "works as ...", because the
  skill check proves skill, not employment.
* Any learner who has picked that path can book. A mentor on the path is not needed.
* A learner under 18 confirms that a guardian or facilitator will be nearby, and everybody confirms the short code of
  conduct. Guardian consent is already collected at sign-up.
* The contact (link or the host's own number) is shown only to the host and to the learner who booked the slot.
* The call is unpaid and never touches the payout ledger.
* Everything is read through the caller's own user id in this layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app import timeutil
from app.errors import ApiError
from app.models.calls import BookIn, FeedbackIn, SlotIn
from app.services import catalog, events, matching, notifications, opportunities, teacher_assessment

IST = timezone(timedelta(hours=5, minutes=30))
MIN_LEAD = timedelta(hours=2)  # a host cannot post a slot that starts sooner than this
BOOK_LEAD = timedelta(hours=1)  # a learner cannot book a slot that starts sooner than this
MAX_AHEAD = timedelta(days=30)
DAY_START_HOUR = 7  # calls are between 7 am and 9 pm Indian time
DAY_END_HOUR = 21
MAX_OPEN_SLOTS = 10
MAX_LISTED = 20
PAST_LISTED = 10
MINORS = 18


def _end(slot: dict[str, Any]) -> datetime:
    return timeutil.ensure_aware(slot["starts_at"]) + timedelta(minutes=slot["minutes"])


def verified_for(teacher: dict[str, Any], career: dict[str, Any]) -> list[str]:
    """The skills this mentor has verified that the career needs. Empty when they are below tier 1."""
    if teacher.get("tier", 0) < 1:
        return []
    required = {r["skill"] for r in career["required_skills"]}
    return sorted(matching.verified_skill_set(teacher) & required)


def verified_areas(teacher: dict[str, Any], career: dict[str, Any]) -> list[dict[str, Any]]:
    """The skill checks the mentor actually passed that back this career, by name (for example "Digital marketing for local shops").

    One check proves a bundle of skills, so listing the skills one by one would claim more than was tested. The label
    names the check instead. Only checks that still count (approved proof, passed test) and that touch the career are listed.
    """
    backed = set(verified_for(teacher, career))
    if not backed:
        return []
    evidence = teacher.get("evidence") or {}
    out = []
    for area_id in teacher_assessment.effective_areas(teacher.get("passed_areas", []), evidence.get("areas")):
        area = catalog.test_area(area_id)
        if area and backed & set(area.get("verifies", [])):
            out.append({"id": area_id, "name": area["name"]})
    return out


def hostable_careers(teacher: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for career in catalog.careers():
        if verified_for(teacher, career):
            out.append({"career_id": career["career_id"], "name": career["name"], "verified_in": verified_areas(teacher, career)})
    return out


def check_time(starts_at: datetime, minutes: int, now: datetime) -> None:
    """Between 7 am and 9 pm Indian time, from two hours to thirty days ahead. Raises a plain error otherwise."""
    start = starts_at.astimezone(timezone.utc)
    if start < now + MIN_LEAD:
        raise ApiError(422, "slot_too_soon", "Pick a time at least two hours from now.", "")
    if start > now + MAX_AHEAD:
        raise ApiError(422, "slot_too_far", "Pick a time within the next 30 days.", "")
    local = start.astimezone(IST)
    end_local = local + timedelta(minutes=minutes)
    if local.hour < DAY_START_HOUR or end_local.date() != local.date() or end_local.hour * 60 + end_local.minute > DAY_END_HOUR * 60:
        raise ApiError(422, "slot_hours", "Calls are between 7 am and 9 pm.", "Pick a time in the daytime or evening.")


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _host_card(teacher: dict[str, Any], career: dict[str, Any], learner_language: str | None = None) -> dict[str, Any]:
    return {
        "teacher_id": teacher["_id"],  # the profile id; the account id is never sent to another user
        "name": teacher["name"],
        "roles": teacher["roles"],
        "languages": teacher["languages"],
        "district": teacher["district"],
        "block": teacher["block"],
        "verified_in": verified_areas(teacher, career),
        "speaks_your_language": learner_language in teacher["languages"] if learner_language else None,
    }


def _when(slot: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "id": slot["_id"],
        "career_id": slot["career_id"],
        "starts_at": timeutil.ensure_aware(slot["starts_at"]),
        "minutes": slot["minutes"],
        "ended": _end(slot) <= now,
    }


async def _host_slot_view(db: AsyncIOMotorDatabase, slot: dict[str, Any], now: datetime) -> dict[str, Any]:
    career = catalog.career(slot["career_id"])
    learner = None
    if slot.get("student_id"):
        s = await db["student_profiles"].find_one({"user_id": slot["student_id"]}) or {}
        u = await db["users"].find_one({"_id": slot["student_id"]}, {"language": 1}) or {}
        first = (s.get("name") or "").split(" ")[0]
        learner = {"first_name": first, "age_band": s.get("age_band"), "language": u.get("language", "en"), "guardian_near": bool(slot.get("guardian_near"))}
    return {
        **_when(slot, now),
        "career_name": career["name"] if career else {"en": slot["career_id"]},
        "status": slot["status"],
        "contact_kind": slot["contact_kind"],
        "contact": slot["contact"],  # the host's own, shown back to them
        "learner": learner,
        "outcome": slot.get("outcome"),
        "rating": slot.get("rating"),
    }


async def _own_booking_view(db: AsyncIOMotorDatabase, slot: dict[str, Any], now: datetime) -> dict[str, Any]:
    career = catalog.career(slot["career_id"])
    teacher = await db["teacher_profiles"].find_one({"_id": slot["teacher_profile_id"]})
    return {
        **_when(slot, now),
        "career_name": career["name"] if career else {"en": slot["career_id"]},
        "host": _host_card(teacher, career) if teacher and career else None,
        "contact_kind": slot["contact_kind"],
        "contact": slot["contact"],  # only the learner who booked the slot ever receives this
        "outcome": slot.get("outcome"),
        "rating": slot.get("rating"),
    }


# ---------------------------------------------------------------------------
# The mentor's side
# ---------------------------------------------------------------------------


async def _my_teacher(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    t = await db["teacher_profiles"].find_one({"user_id": user["_id"]})
    if t is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")
    return t


async def host_overview(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    teacher = await _my_teacher(db, user)
    now = timeutil.utcnow()
    careers = hostable_careers(teacher)
    slots = [s async for s in db["calls"].find({"teacher_id": user["_id"]}).sort("starts_at", 1)]
    upcoming = [s for s in slots if s["status"] in ("open", "booked") and not _end(s) <= now]
    past = [s for s in slots if s["status"] == "booked" and _end(s) <= now][-PAST_LISTED:]
    return {
        "offers_calls": bool(teacher.get("offers_calls")),
        "can_host": bool(careers),
        "careers": careers,
        "upcoming": [await _host_slot_view(db, s, now) for s in upcoming],
        "past": [await _host_slot_view(db, s, now) for s in reversed(past)],
        "limits": {"max_open": MAX_OPEN_SLOTS, "minutes": [30, 45]},
    }


async def set_offering(db: AsyncIOMotorDatabase, user: dict[str, Any], on: bool) -> dict[str, Any]:
    teacher = await _my_teacher(db, user)
    if on and not hostable_careers(teacher):
        raise ApiError(409, "not_verified", "Finish your skill check and proof first.", "Calls are for mentors verified in a skill.")
    await db["teacher_profiles"].update_one({"_id": teacher["_id"]}, {"$set": {"offers_calls": on, "updated_at": timeutil.utcnow()}})
    if not on:  # switching off takes the open times down; a call someone already booked stays
        await db["calls"].update_many({"teacher_id": user["_id"], "status": "open"}, {"$set": {"status": "cancelled", "cancelled_at": timeutil.utcnow()}})
    return await host_overview(db, user)


async def add_slot(db: AsyncIOMotorDatabase, user: dict[str, Any], body: SlotIn) -> dict[str, Any]:
    teacher = await _my_teacher(db, user)
    if not teacher.get("offers_calls"):
        raise ApiError(409, "calls_off", "Switch on career calls first.", "")
    career = catalog.career(body.career_id)
    if career is None or not verified_for(teacher, career):
        raise ApiError(409, "not_hostable", "You can offer calls only for careers whose skill you have verified.", "")
    try:
        contact = body.checked_contact()
    except ValueError:
        raise ApiError(422, "contact_invalid", "Check the link or phone number.", "A link starts with https:// and a phone number has 10 digits.")

    now = timeutil.utcnow()
    start = body.starts_at.astimezone(timezone.utc)
    check_time(start, body.minutes, now)

    live = [s async for s in db["calls"].find({"teacher_id": user["_id"], "status": {"$in": ["open", "booked"]}})]
    live = [s for s in live if _end(s) > now]
    if len(live) >= MAX_OPEN_SLOTS:
        raise ApiError(409, "too_many_slots", "You already have the most times we allow.", "Cancel one first.")
    end = start + timedelta(minutes=body.minutes)
    if any(timeutil.ensure_aware(s["starts_at"]) < end and start < _end(s) for s in live):
        raise ApiError(409, "slot_overlaps", "You already have a call at that time.", "")

    slot = {
        "_id": uuid.uuid4().hex,
        "teacher_id": user["_id"],
        "teacher_profile_id": teacher["_id"],
        "career_id": body.career_id,
        "starts_at": start,
        "minutes": body.minutes,
        "contact_kind": body.contact_kind,
        "contact": contact,
        "status": "open",
        "student_id": None,
        "booked_at": None,
        "guardian_near": None,
        "outcome": None,
        "rating": None,
        "created_at": now,
    }
    await db["calls"].insert_one(slot)
    return await _host_slot_view(db, slot, now)


async def host_cancel(db: AsyncIOMotorDatabase, user: dict[str, Any], slot_id: str) -> dict[str, Any]:
    now = timeutil.utcnow()
    slot = await db["calls"].find_one({"_id": slot_id, "teacher_id": user["_id"]})  # scoped to the caller here
    if slot is None:
        raise ApiError(404, "call_not_found", "We could not find that call.", "")
    if slot["status"] == "cancelled":
        return await _host_slot_view(db, slot, now)  # cancelling twice is one cancel
    if timeutil.ensure_aware(slot["starts_at"]) <= now:
        raise ApiError(409, "call_started", "This call has already started.", "")
    claimed = await db["calls"].find_one_and_update(
        {"_id": slot_id, "status": slot["status"]}, {"$set": {"status": "cancelled", "cancelled_at": now}}, return_document=ReturnDocument.BEFORE
    )
    if claimed is not None and claimed.get("student_id"):
        await notifications.notify(db, claimed["student_id"], "call_cancelled", "/calls")
    return await _host_slot_view(db, {**slot, "status": "cancelled"}, now)


# ---------------------------------------------------------------------------
# The learner's side
# ---------------------------------------------------------------------------


async def _learner(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    s = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if s is None:
        raise ApiError(409, "profile_required", "Please finish your profile first.", "")
    return s


async def overview(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    """The times open for the learner's path, and the calls they have booked. Contact details are only in `mine`."""
    student = await _learner(db, user)
    journey = await opportunities.current_journey(db, user)
    career = catalog.career(journey["career_id"])
    now = timeutil.utcnow()

    mine = [s async for s in db["calls"].find({"student_id": user["_id"], "status": "booked"}).sort("starts_at", 1)]
    upcoming = [s for s in mine if not _end(s) <= now]
    past = [s for s in mine if _end(s) <= now][-PAST_LISTED:]

    language = user.get("language", "en")
    hosts: dict[str, dict[str, Any] | None] = {}
    open_slots = []
    cursor = db["calls"].find({"career_id": journey["career_id"], "status": "open", "starts_at": {"$gt": now + BOOK_LEAD}}).sort("starts_at", 1)
    async for slot in cursor:
        if slot["teacher_profile_id"] not in hosts:
            t = await db["teacher_profiles"].find_one({"_id": slot["teacher_profile_id"]})
            hosts[slot["teacher_profile_id"]] = t if t and t.get("offers_calls") and verified_for(t, career) else None
        teacher = hosts[slot["teacher_profile_id"]]
        if teacher is None:
            continue
        open_slots.append({**_when(slot, now), "host": _host_card(teacher, career, language)})
        if len(open_slots) >= MAX_LISTED:
            break

    return {
        "career_id": journey["career_id"],
        "career_name": career["name"] if career else {"en": journey["career_id"]},
        "needs_guardian": student["age"] < MINORS,
        "can_book": not upcoming,  # one call at a time, so one learner cannot hold every time
        "slots": open_slots,
        "upcoming": [await _own_booking_view(db, s, now) for s in upcoming],
        "past": [await _own_booking_view(db, s, now) for s in reversed(past)],
    }


async def book(db: AsyncIOMotorDatabase, user: dict[str, Any], slot_id: str, body: BookIn) -> dict[str, Any]:
    student = await _learner(db, user)
    now = timeutil.utcnow()
    slot = await db["calls"].find_one({"_id": slot_id})
    if slot is None or slot["status"] == "cancelled":
        raise ApiError(404, "call_not_found", "This time is no longer there.", "Pick another time.")
    if slot["status"] == "booked":
        if slot["student_id"] == user["_id"]:
            return await _own_booking_view(db, slot, now)  # the same booking sent twice is one booking
        raise ApiError(409, "call_taken", "Someone else just booked this time.", "Pick another time.")

    on_path = await db["journeys"].find_one({"student_id": user["_id"], "career_id": slot["career_id"], "state": {"$ne": "abandoned"}})
    if on_path is None:
        raise ApiError(409, "call_wrong_path", "This call is for a different path.", "Pick a time listed for your path.")
    if not body.agreed:
        raise ApiError(409, "call_conduct_needed", "Please tick that you will follow the call rules.", "")
    if student["age"] < MINORS and not body.guardian_near:
        raise ApiError(409, "call_guardian_needed", "A guardian or facilitator must be nearby during the call.", "Ask them to sit with you, then tick the box.")

    holding = [s async for s in db["calls"].find({"student_id": user["_id"], "status": "booked"})]
    if any(_end(s) > now for s in holding):
        raise ApiError(409, "call_limit", "You already have a call booked.", "Finish that one first.")

    teacher = await db["teacher_profiles"].find_one({"_id": slot["teacher_profile_id"]})
    career = catalog.career(slot["career_id"])
    if teacher is None or career is None or not teacher.get("offers_calls") or not verified_for(teacher, career):
        raise ApiError(409, "call_unavailable", "This mentor is not offering calls right now.", "Pick another time.")

    claimed = await db["calls"].find_one_and_update(
        {"_id": slot_id, "status": "open", "starts_at": {"$gt": now + BOOK_LEAD}},
        {"$set": {"status": "booked", "student_id": user["_id"], "booked_at": now, "guardian_near": bool(body.guardian_near)}},
        return_document=ReturnDocument.AFTER,
    )
    if claimed is None:
        raise ApiError(409, "call_taken", "That time is no longer open.", "Pick another time.")
    await events.record(db, "career_call_booked", user["_id"], ref=slot_id, block=student["block"], district=student["district"], skill_tags=verified_for(teacher, career))
    await notifications.notify(db, slot["teacher_id"], "call_booked", "/t/calls")
    return await _own_booking_view(db, claimed, now)


async def cancel(db: AsyncIOMotorDatabase, user: dict[str, Any], slot_id: str) -> dict[str, Any]:
    """The learner gives the time back. It opens again for someone else, and the host is told."""
    now = timeutil.utcnow()
    slot = await db["calls"].find_one({"_id": slot_id, "student_id": user["_id"]})  # scoped to the caller here
    if slot is None:
        raise ApiError(404, "call_not_found", "We could not find that call.", "")
    if timeutil.ensure_aware(slot["starts_at"]) <= now:
        raise ApiError(409, "call_started", "This call has already started.", "")
    claimed = await db["calls"].find_one_and_update(
        {"_id": slot_id, "student_id": user["_id"], "status": "booked"},
        {"$set": {"status": "open", "student_id": None, "booked_at": None, "guardian_near": None}},
        return_document=ReturnDocument.BEFORE,
    )
    if claimed is not None:
        await notifications.notify(db, slot["teacher_id"], "call_cancelled", "/t/calls")
    return {"cancelled": True}


async def feedback(db: AsyncIOMotorDatabase, user: dict[str, Any], slot_id: str, body: FeedbackIn) -> dict[str, Any]:
    """After the call the learner says whether it happened and how useful it was. Only the learner records it."""
    now = timeutil.utcnow()
    slot = await db["calls"].find_one({"_id": slot_id, "student_id": user["_id"], "status": "booked"})  # scoped to the caller here
    if slot is None:
        raise ApiError(404, "call_not_found", "We could not find that call.", "")
    if _end(slot) > now:
        raise ApiError(409, "call_not_ended", "The call has not finished yet.", "")
    if slot.get("outcome"):
        return await _own_booking_view(db, slot, now)  # answering twice keeps the first answer
    outcome = "held" if body.took_place else "missed"
    rating = body.rating if body.took_place else None
    claimed = await db["calls"].find_one_and_update(
        {"_id": slot_id, "outcome": None}, {"$set": {"outcome": outcome, "rating": rating, "recorded_at": now}}, return_document=ReturnDocument.AFTER
    )
    if claimed is None:
        return await _own_booking_view(db, await db["calls"].find_one({"_id": slot_id}) or slot, now)
    student = await db["student_profiles"].find_one({"user_id": user["_id"]}) or {}
    await events.record(db, f"career_call_{outcome}", user["_id"], ref=slot_id, block=student.get("block"), district=student.get("district"))
    return await _own_booking_view(db, claimed, now)
