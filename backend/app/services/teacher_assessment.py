"""Teacher skill check (CLAUDE.md section 10): claim, evidence, practical test, outcomes.

Tier 1 needs two layers: evidence a reviewer has approved, and a passed practical test. The test is five sample
descriptions of learners' work with expert scores kept on the server; a teacher passes when at least 4 of 5 of their
scores are within one point of the expert's. Expert scores are never sent to the client. Tier 2 (proven by
outcomes) is not awarded here: it needs completed journeys, which come with later milestones.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app import timeutil
from app.errors import ApiError
from app.models.mentoring import CredentialIn
from app.services import catalog, events

MAX_CREDENTIALS = 20  # room for proof of each skill area, with a few spare
REVIEW_TIMEOUT = timedelta(minutes=5)  # a review stuck longer than this (a crash) may be started again


def rule() -> dict[str, int]:
    return catalog.teacher_tests()["pass_rule"]


def score_attempt(area: dict[str, Any], scores: dict[str, int]) -> int:
    """How many of the samples the teacher scored within the allowed distance of the expert's score."""
    within = rule()["within"]
    return sum(1 for item in area["items"] if abs(scores[item["id"]] - item["expert_score"]) <= within)


def effective_areas(passed_areas: list[str], proof_areas: list[str] | None) -> list[str]:
    """The skill areas that count. When the approved proof was reviewed for particular areas (the AI review records
    them), only passed tests in those areas count: a mobile-repair certificate does not back a tailoring test."""
    if not proof_areas:
        return list(passed_areas)
    return [a for a in passed_areas if a in proof_areas]


def tier_for(evidence_status: str, passed_areas: list[str], current_tier: int = 0, proof_areas: list[str] | None = None) -> int:
    """Tier 1 needs approved evidence and a passed test. A tier 2 already earned from outcomes is never lowered here."""
    if current_tier >= 2:
        return current_tier
    return 1 if evidence_status == "verified" and effective_areas(passed_areas, proof_areas) else 0


def verified_tags(passed_areas: list[str]) -> list[str]:
    tags: list[str] = []
    for area_id in passed_areas:
        area = catalog.test_area(area_id)
        for tag in (area or {}).get("verifies", []):
            if tag not in tags:
                tags.append(tag)
    return tags


def recompute(doc: dict[str, Any]) -> dict[str, Any]:
    """The fields that follow from the evidence status and the passed tests. Pure: the caller stores them."""
    evidence = doc.get("evidence") or {}
    status = evidence.get("status", "none")
    passed = effective_areas(doc.get("passed_areas", []), evidence.get("areas"))
    proven = set(verified_tags(passed))
    skills = {s["tag"]: dict(s) for s in doc.get("skills", [])}
    for tag in proven:
        skills.setdefault(tag, {"tag": tag, "level": None, "verified": False})
    for tag, entry in skills.items():
        entry["verified"] = tag in proven and status == "verified"
    return {"skills": list(skills.values()), "tier": tier_for(status, doc.get("passed_areas", []), doc.get("tier", 0), evidence.get("areas"))}


async def _store(db: AsyncIOMotorDatabase, doc: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    merged = {**doc, **changes}
    derived = recompute(merged)
    update = {**changes, **derived, "updated_at": timeutil.utcnow()}
    await db["teacher_profiles"].update_one({"_id": doc["_id"]}, {"$set": update})
    return {**doc, **update}


async def _my_profile(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["teacher_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(404, "profile_not_found", "No profile yet.", "Create one first.")
    return doc


# ---------------------------------------------------------------------------
# Evidence (layer 2)
# ---------------------------------------------------------------------------


def is_reviewing(evidence: dict[str, Any] | None) -> bool:
    """A review of new proof is running right now. This is a flag, separate from the status, so a teacher who is already
    approved for one skill keeps that approval (and their tier) while a proof for another skill is being read."""
    since = (evidence or {}).get("reviewing_since")
    return since is not None and timeutil.utcnow() - timeutil.ensure_aware(since) < REVIEW_TIMEOUT


def credential_state(cred: dict[str, Any], evidence: dict[str, Any] | None) -> tuple[str, list[str]]:
    """`approved` (locked, filed under the skills it backs) or `new`. A proof approved before proofs were tracked one by one
    counts as approved for the skills the review recorded."""
    evidence = evidence or {}
    if cred.get("state") == "approved":
        return "approved", list(cred.get("approved_areas", []))
    if "state" not in cred and evidence.get("status") == "verified" and evidence.get("reviewed_by"):
        return "approved", list(evidence.get("areas", []))
    return "new", []


def credential_view(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c["id"],
        "kind": c["kind"],
        "title": c["title"],
        "note": c["note"],
        "photos": len(c.get("photos", [])),
        "added_at": timeutil.ensure_aware(c["added_at"]),
    }


async def add_credential(db: AsyncIOMotorDatabase, user: dict[str, Any], body: CredentialIn) -> dict[str, Any]:
    doc = await _my_profile(db, user)
    existing = doc.get("credentials", [])
    if len(existing) >= MAX_CREDENTIALS:
        raise ApiError(409, "too_many_credentials", "You have added the most we can keep.", "Ask the team if you need to add more.")
    entry = {"id": uuid.uuid4().hex[:12], "kind": body.kind, "title": body.title, "note": body.note, "added_at": timeutil.utcnow(), "state": "new"}
    current = doc.get("evidence") or {}
    if is_reviewing(current):
        raise ApiError(409, "review_in_progress", "Your proof is being checked right now.", "Wait a moment, then try again.")
    if current.get("status") == "verified":
        evidence = current  # a skill that is already approved stays approved; the new proof is read when it is submitted
    else:
        evidence = {**current, "status": "pending", "submitted_at": timeutil.utcnow()}
    out = await _store(db, doc, {"credentials": [*existing, entry], "evidence": evidence})
    return {"credentials": [credential_view(c) for c in out["credentials"]], "evidence_status": out["evidence"]["status"]}


async def pending_review(db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    out = []
    async for doc in db["teacher_profiles"].find({"evidence.status": "pending"}).sort("evidence.submitted_at", 1):
        out.append(
            {
                "teacher_id": doc["_id"],
                "name": doc["name"],
                "roles": doc["roles"],
                "district": doc["district"],
                "block": doc["block"],
                "passed_areas": doc.get("passed_areas", []),
                "credentials": [credential_view(c) for c in doc.get("credentials", [])],
                "submitted_at": timeutil.ensure_aware(doc["evidence"]["submitted_at"]) if doc["evidence"].get("submitted_at") else None,
            }
        )
    return out


async def review_evidence(db: AsyncIOMotorDatabase, admin: dict[str, Any], teacher_id: str, decision: str, note: str) -> dict[str, Any]:
    doc = await db["teacher_profiles"].find_one({"_id": teacher_id})
    if doc is None:
        raise ApiError(404, "teacher_not_found", "We could not find that teacher.", "")
    current = doc.get("evidence") or {}
    ai_approved = current.get("status") == "verified" and current.get("reviewed_by") == "ai"
    if current.get("status") != "pending" and not ai_approved:  # a person may also confirm (or overturn) an AI approval
        raise ApiError(409, "nothing_to_review", "This teacher has nothing waiting for review.", "")
    status = "verified" if decision == "approve" else "rejected"
    evidence = {**current, "status": status, "note": note, "reviewed_at": timeutil.utcnow(), "reviewed_by": admin["_id"], "reasons": []}
    if ai_approved and status == "verified":
        evidence["confirmed_by"] = admin["_id"]  # lifts the lower capacity of an AI-only approval
    out = await _store(db, doc, {"evidence": evidence})
    await db["audit_logs"].insert_one(
        {"_id": uuid.uuid4().hex, "ts": timeutil.utcnow(), "actor": admin["_id"], "action": f"teacher_evidence_{status}", "ref": teacher_id}
    )
    if status == "verified":
        tags = [s["tag"] for s in out["skills"] if s["verified"]]
        await events.record(db, "teacher_verified", doc["user_id"], ref=doc["_id"], block=doc["block"], district=doc["district"], skill_tags=tags)
    return {"teacher_id": teacher_id, "evidence_status": status, "tier": out["tier"]}


# ---------------------------------------------------------------------------
# Practical test (layer 3)
# ---------------------------------------------------------------------------


def _area_or_404(area_id: str) -> dict[str, Any]:
    area = catalog.test_area(area_id)
    if area is None:
        raise ApiError(404, "area_not_found", "We could not find that skill check.", "Pick one from the list.")
    return area


async def attempts_used(db: AsyncIOMotorDatabase, user_id: str, area_id: str) -> int:
    return await db["teacher_tests"].count_documents({"user_id": user_id, "area_id": area_id})


async def areas_view(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> list[dict[str, Any]]:
    doc = await _my_profile(db, user)
    max_attempts = rule()["max_attempts"]
    out = []
    for area in catalog.teacher_tests()["areas"]:
        used = await attempts_used(db, user["_id"], area["id"])
        passed = area["id"] in doc.get("passed_areas", [])
        out.append(
            {
                "id": area["id"],
                "name": area["name"],
                "career_ids": area["career_ids"],
                "passed": passed,
                "attempts_left": 0 if passed else max(0, max_attempts - used),
            }
        )
    return out


async def area_for_test(db: AsyncIOMotorDatabase, user: dict[str, Any], area_id: str) -> dict[str, Any]:
    """The samples to score. The expert's scores are not part of this."""
    area = _area_or_404(area_id)
    doc = await _my_profile(db, user)
    used = await attempts_used(db, user["_id"], area_id)
    return {
        "id": area["id"],
        "name": area["name"],
        "scale": catalog.teacher_tests()["scale"],
        "items": [{"id": i["id"], "work": i["work"]} for i in area["items"]],
        "pass_rule": {"needed": rule()["needed"], "of": rule()["items"], "within": rule()["within"]},
        "passed": area_id in doc.get("passed_areas", []),
        "attempts_left": max(0, rule()["max_attempts"] - used),
    }


async def submit_test(db: AsyncIOMotorDatabase, user: dict[str, Any], area_id: str, scores: dict[str, int]) -> dict[str, Any]:
    area = _area_or_404(area_id)
    doc = await _my_profile(db, user)
    if area_id in doc.get("passed_areas", []):
        raise ApiError(409, "already_passed", "You have already passed this skill check.", "")
    ids = {i["id"] for i in area["items"]}
    if set(scores) != ids:
        raise ApiError(422, "scores_incomplete", "Please score every sample.", "Give each one a score from 1 to 4.")
    used = await attempts_used(db, user["_id"], area_id)
    if used >= rule()["max_attempts"]:
        raise ApiError(409, "no_attempts_left", "You have used all your tries for this skill check.", "Ask the team to look at your case.")

    close = score_attempt(area, scores)
    passed = close >= rule()["needed"]
    await db["teacher_tests"].insert_one(
        {
            "_id": uuid.uuid4().hex,
            "user_id": user["_id"],
            "area_id": area_id,
            "attempt": used + 1,
            "scores": scores,
            "close": close,
            "passed": passed,
            "created_at": timeutil.utcnow(),
        }
    )
    tier = doc.get("tier", 0)
    if passed:
        out = await _store(db, doc, {"passed_areas": [*doc.get("passed_areas", []), area_id]})
        tier = out["tier"]
        await events.record(db, "teacher_test_passed", user["_id"], ref=area_id, block=doc["block"], district=doc["district"], skill_tags=area["verifies"])
    return {
        "passed": passed,
        "close": close,
        "needed": rule()["needed"],
        "of": rule()["items"],
        "attempts_left": max(0, rule()["max_attempts"] - used - 1),
        "tier": tier,
        "awaiting_evidence": passed and tier == 0,
    }
