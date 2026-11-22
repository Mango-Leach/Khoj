"""Student and teacher profiles. Every read and write is scoped to the caller's user id."""
from __future__ import annotations

import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app import timeutil
from app.errors import ApiError, validation_payload
from app.services import catalog, journeys, teacher_assessment
from app.models.profiles import (
    StudentProfileIn,
    StudentProfilePatch,
    TeacherProfileIn,
    TeacherProfilePatch,
    age_band,
)


def _invalid(exc: ValidationError) -> ApiError:
    body = validation_payload([dict(e) for e in exc.errors()])
    return ApiError(422, body["code"], body["message"], body["hint"], fields=body["fields"])


async def _add_role(db: AsyncIOMotorDatabase, user_id: str, role: str) -> None:
    await db["users"].update_one({"_id": user_id}, {"$addToSet": {"roles": role}})


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


def student_view(doc: dict[str, Any]) -> dict[str, Any]:
    consent = doc.get("guardian_consent") or {}
    consent_at = consent.get("at")
    return {
        "name": doc["name"],
        "age": doc["age"],
        "age_band": doc["age_band"],
        "grade": doc["grade"],
        "state": doc["state"],
        "district": doc["district"],
        "block": doc["block"],
        "guardian_consent": bool(consent.get("given")),
        "guardian_consent_at": timeutil.ensure_aware(consent_at) if consent_at else None,  # always UTC-aware in the API
    }


def _consent(given: bool, previous: dict[str, Any] | None) -> dict[str, Any] | None:
    if not given:
        return None
    if previous and previous.get("given"):
        return previous  # keep the original timestamp
    # Declared in the app by the student. Verifiable parental consent is not built; the DPDP
    # position for under-18s needs legal review before launch.
    return {"given": True, "at": timeutil.utcnow(), "method": "declared_in_app"}


async def create_student(db: AsyncIOMotorDatabase, user: dict[str, Any], payload: StudentProfileIn) -> dict[str, Any]:
    if "teacher" in user.get("roles", []):
        raise ApiError(409, "role_conflict", "This account is registered as a teacher.", "Use a different number for a student account.")
    now = timeutil.utcnow()
    doc = {
        "_id": uuid.uuid4().hex,
        "user_id": user["_id"],
        "name": payload.name,
        "age": payload.age,
        "age_band": age_band(payload.age),
        "grade": payload.grade,
        "state": payload.state,
        "district": payload.district,
        "block": payload.block,
        "guardian_consent": _consent(payload.guardian_consent, None),
        "interests": [],
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db["student_profiles"].insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(409, "profile_exists", "A profile already exists.", "Edit it instead.")
    await _add_role(db, user["_id"], "student")
    return student_view(doc)


async def get_student(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")
    return student_view(doc)


async def update_student(db: AsyncIOMotorDatabase, user: dict[str, Any], patch: StudentProfilePatch) -> dict[str, Any]:
    doc = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")

    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    merged = {
        "name": doc["name"], "age": doc["age"], "grade": doc["grade"], "state": doc["state"],
        "district": doc["district"], "block": doc["block"],
        "guardian_consent": bool((doc.get("guardian_consent") or {}).get("given")),
        **changes,
    }
    try:
        valid = StudentProfileIn(**merged)  # re-runs every rule, including consent for under-18s
    except ValidationError as exc:
        raise _invalid(exc)

    update = {
        "name": valid.name, "age": valid.age, "age_band": age_band(valid.age), "grade": valid.grade,
        "district": valid.district, "block": valid.block,
        "guardian_consent": _consent(valid.guardian_consent, doc.get("guardian_consent")),
        "updated_at": timeutil.utcnow(),
    }
    await db["student_profiles"].update_one({"_id": doc["_id"]}, {"$set": update})
    return student_view({**doc, **update})


# ---------------------------------------------------------------------------
# Teachers, mentors, facilitators and experts
# ---------------------------------------------------------------------------

TIER_CAPACITY = {0: 0, 1: 5, 2: 15}  # CLAUDE.md section 10 (illustrative limits)
AI_ONLY_CAP = 3  # a tier 1 teacher approved by the AI review alone holds fewer learners until a person confirms them


def capacity_limit(doc: dict[str, Any]) -> int:
    tier = doc.get("tier", 0)
    limit = TIER_CAPACITY.get(tier, 0)
    evidence = doc.get("evidence") or {}
    if tier == 1 and evidence.get("reviewed_by") == "ai" and not evidence.get("confirmed_by"):
        return min(limit, AI_ONLY_CAP)
    return limit


def teacher_view(doc: dict[str, Any], active: int = 0) -> dict[str, Any]:
    tier = doc.get("tier", 0)
    limit = capacity_limit(doc)
    evidence = doc.get("evidence") or {}
    results = evidence.get("photo_results") or {}
    passed = set(doc.get("passed_areas", []))
    reviewing = teacher_assessment.is_reviewing(evidence)
    status = evidence.get("status", "none")
    if status == "reviewing" and not reviewing:
        status = "pending"  # a review that never finished (a crash) must not leave the page waiting for ever
    return {
        "name": doc["name"],
        "roles": doc["roles"],
        "skills": doc["skills"],
        "languages": doc["languages"],
        "state": doc["state"],
        "district": doc["district"],
        "block": doc["block"],
        "weekly_hours": doc["weekly_hours"],
        "tier": tier,
        "trust": doc.get("trust"),
        "capacity": {"limit": limit, "free": max(0, limit - active)},
        "evidence": {
            "status": status,
            "reviewing": reviewing,
            "note": evidence.get("note", "") if status == "rejected" else "",
            "reasons": evidence.get("reasons", []),
        },
        "credentials": [
            {
                "id": c["id"],
                "kind": c["kind"],
                "title": c["title"],
                "note": c["note"],
                "added_at": timeutil.ensure_aware(c["added_at"]),
                # approved proofs are filed under the skills they back, with whether that skill's test is passed
                "state": teacher_assessment.credential_state(c, evidence)[0],
                "areas": [
                    {"id": a, "name": area["name"], "test_passed": a in passed}
                    for a in teacher_assessment.credential_state(c, evidence)[1]
                    if (area := catalog.test_area(a)) is not None
                ],
                # per photo: good is true or false once reviewed and null before; reasons are stable codes
                "photos": [
                    {"id": pid, "good": (results.get(pid) or {}).get("good"), "reasons": (results.get(pid) or {}).get("reasons", [])}
                    for pid in c.get("photos", [])
                ],
            }
            for c in doc.get("credentials", [])
        ],
        "passed_areas": doc.get("passed_areas", []),
        "verified_areas": verified_areas(doc),
    }


def verified_areas(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The skill areas this teacher can be matched on: a passed test AND approved proof for that area.
    Empty until the proof is approved, so the home page never shows a skill that is only half proven."""
    evidence = doc.get("evidence") or {}
    if evidence.get("status") != "verified":
        return []
    out = []
    for area_id in teacher_assessment.effective_areas(doc.get("passed_areas", []), evidence.get("areas")):
        area = catalog.test_area(area_id)
        if area:
            out.append({"id": area_id, "name": area["name"]})
    return out


async def _teacher_with_load(db: AsyncIOMotorDatabase, doc: dict[str, Any]) -> dict[str, Any]:
    counts = await journeys.active_counts(db, [doc["user_id"]])
    return teacher_view(doc, counts.get(doc["user_id"], 0))


def _skill_entries(tags: list[str], existing: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    known = {s["tag"]: s for s in (existing or [])}
    return [known.get(tag, {"tag": tag, "level": None, "verified": False}) for tag in tags]


async def create_teacher(db: AsyncIOMotorDatabase, user: dict[str, Any], payload: TeacherProfileIn) -> dict[str, Any]:
    if "student" in user.get("roles", []):
        raise ApiError(409, "role_conflict", "This account is registered as a student.", "Use a different number for a teacher account.")
    now = timeutil.utcnow()
    doc = {
        "_id": uuid.uuid4().hex,
        "user_id": user["_id"],
        "name": payload.name,
        "roles": payload.roles,
        "skills": _skill_entries(payload.skills),  # unverified claims until the skill assessment
        "languages": payload.languages,
        "state": payload.state,
        "district": payload.district,
        "block": payload.block,
        "weekly_hours": payload.weekly_hours,
        "tier": 0,  # unverified: cannot be matched until the skill check is passed and the evidence approved
        "trust": None,
        "evidence": {"status": "none"},
        "credentials": [],
        "passed_areas": [],
        "payout_account_ref": None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db["teacher_profiles"].insert_one(doc)
    except DuplicateKeyError:
        raise ApiError(409, "profile_exists", "A profile already exists.", "Edit it instead.")
    await _add_role(db, user["_id"], "teacher")
    return teacher_view(doc)


async def get_teacher(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["teacher_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")
    return await _teacher_with_load(db, doc)


async def update_teacher(db: AsyncIOMotorDatabase, user: dict[str, Any], patch: TeacherProfilePatch) -> dict[str, Any]:
    doc = await db["teacher_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")

    changes = patch.model_dump(exclude_unset=True, exclude_none=True)
    merged = {
        "name": doc["name"], "roles": doc["roles"], "skills": [s["tag"] for s in doc["skills"]],
        "languages": doc["languages"], "state": doc["state"], "district": doc["district"],
        "block": doc["block"], "weekly_hours": doc["weekly_hours"],
        **changes,
    }
    try:
        valid = TeacherProfileIn(**merged)
    except ValidationError as exc:
        raise _invalid(exc)

    update = {
        "name": valid.name, "roles": valid.roles, "skills": _skill_entries(valid.skills, doc["skills"]),
        "languages": valid.languages, "district": valid.district, "block": valid.block,
        "weekly_hours": valid.weekly_hours, "updated_at": timeutil.utcnow(),
    }
    update.update(teacher_assessment.recompute({**doc, **update}))  # proven skills stay, whatever the teacher edits
    await db["teacher_profiles"].update_one({"_id": doc["_id"]}, {"$set": update})
    return await _teacher_with_load(db, {**doc, **update})
