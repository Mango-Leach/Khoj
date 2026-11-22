"""Career assessments and path selection.

An assessment ranks the careers for one learner from their confirmed intake (CLAUDE.md section 6, steps 6 and 7).
The ranking and the baseline reasons are instant and need no AI. Afterwards `enrich` may replace the reasons
of the top paths with a model-written sentence, but only a sentence that passes the guard in reasons.py.
Every learner's data is read through their own user id, in this layer, never trusted from the client.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict

from app import timeutil
from app.errors import ApiError
from app.services import catalog, reasons, resources
from app.services.career_engine import ALSO_COUNT, BEST_COUNT, MIN_RELATED_SKILL, Profile, Ranked, WEIGHTS, rank
from app.services.llm import LLMRequest, LLMService, Task

log = logging.getLogger("khoj.assessments")

ENRICH_TOP = 3  # only the top paths get a model-written reason; the model is slow on a laptop CPU
REASON_VERSION = "reason-v1"
REASON_TRANSLATE_VERSION = "reason-translate-v1"

UNDER18_NOTE = {
    "en": "Until you turn 18 you learn the theory and practise on a training board only. No live electrical or other hazardous work.",
    "hi": "18 साल के होने तक आप सिर्फ़ सिद्धांत सीखते हैं और ट्रेनिंग बोर्ड पर अभ्यास करते हैं। चालू बिजली या दूसरा ख़तरनाक काम नहीं।",
    "mr": "18 वर्षांचे होईपर्यंत तुम्ही फक्त सिद्धांत शिकता आणि ट्रेनिंग बोर्डवर सराव करता. चालू विजेचं किंवा इतर धोकादायक काम नाही.",
}


class ReasonOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reason: str = ""


class ReasonTranslations(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hi: list[str] = []
    mr: list[str] = []


# ---------------------------------------------------------------------------
# Career views
# ---------------------------------------------------------------------------


def career_card(career: dict[str, Any]) -> dict[str, Any]:
    return {
        "career_id": career["career_id"],
        "name": career["name"],
        "family": career["family"],
        "depth": career["depth"],
        "is_stem": career["is_stem"],
        "summary": career["summary"],
        "first_income_step": career["first_income_step"],
        "safety_class": career["safety"]["class"],
        "under18_theory_only": career["safety"]["under18_theory_only"],
        "source_count": len(career["sources"]),
    }


def career_detail(career: dict[str, Any]) -> dict[str, Any]:
    """Everything the details screen shows. Local demand and ranking numbers are not part of it."""
    translated = catalog.careers_i18n().get(career["career_id"], {})
    ladder = []
    for i, rung in enumerate(career["ladder"]):
        title, detail = {"en": rung["title"]}, {"en": rung["detail"]}
        for lang in ("hi", "mr"):
            t = (translated.get(lang) or {}).get("ladder", [])
            if i < len(t):
                title[lang], detail[lang] = t[i]["title"], t[i]["detail"]
        ladder.append({"rung": i + 1, "key": rung["key"], "title": title, "detail": detail})
    t = career["traits"]
    return {
        **career_card(career),
        "ladder": ladder,
        # which languages of the ladder text are machine-translated (labelled as such on screen)
        "machine_translated": [lang for lang in ("hi", "mr") if translated.get(lang)],
        "required_skills": [r["skill"] for r in career["required_skills"]],
        "traits": {"startup_cost": t["startup_cost"], "min_hours_per_week": t["min_hours_per_week"], "needs_travel": t["needs_travel"], "self_employment": t["self_employment"]},
        "safety": {**career["safety"], "under18_note": UNDER18_NOTE},
        "learn": resources.for_career(career["career_id"]),
        "portals": career["learn_links"],  # provider home pages, for careers with no specific course yet
        "sources": career["sources"],
        "opportunity_routes": career["opportunity_routes"],
    }


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------


def _path_view(doc_path: dict[str, Any]) -> dict[str, Any]:
    career = catalog.career(doc_path["career_id"])
    assert career is not None
    return {
        "rank": doc_path["rank"],
        **career_card(career),
        "reason": doc_path["reason"],
        "reason_source": doc_path.get("reason_source", {"en": "template", "hi": "template", "mr": "template"}),
        "matched_skills": doc_path["matched"],
        "related_skills": doc_path["related"],
        "starter": doc_path["starter"],
        "tier": doc_path.get("tier") or ("starter" if doc_path["starter"] else "best"),
        "under18_theory_only": doc_path["under18_theory_only"],
        "explain": {"score": doc_path["score"], "factors": doc_path["factors"], "via": doc_path.get("via")},
    }


def shown_paths(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The paths a learner may see and pick from.

    An assessment saved before the "3 best fits, then up to 3 also worth a look" rule holds up to 10 paths and no tier on
    them, so every one would read as a best fit. Those are cut down here with the same rule the ranking uses: only paths
    with a real link to what the learner said, the first three as best fits, then up to three more that are somewhat
    related. New assessments already carry a tier on every path and are returned as they are.
    """
    paths = doc["paths"]
    if not paths or all(p.get("tier") for p in paths) or "matched" not in paths[0]:
        return paths  # current format (or a bare test record): nothing to repair
    if any(p.get("starter") for p in paths):
        return [{**p, "tier": "starter"} for p in paths[:BEST_COUNT]]
    linked = [p for p in paths if p["matched"] or p["related"] or p.get("via")]
    best = [{**p, "tier": "best"} for p in linked[:BEST_COUNT]]
    also = [{**p, "tier": "also"} for p in linked[BEST_COUNT:] if p["factors"]["skill"] >= MIN_RELATED_SKILL][:ALSO_COUNT]
    return best + also


def assessment_view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "status": "ready",
        "intake_id": doc["intake_id"],
        "enrichment": doc.get("enrichment", "none"),
        "created_at": timeutil.ensure_aware(doc["created_at"]),
        "based_on": doc["based_on"],
        "weights": doc["weights"],
        "paths": [_path_view(p) for p in shown_paths(doc)],
    }


def _profile_from(intake_doc: dict[str, Any], student: dict[str, Any]) -> Profile:
    ex = intake_doc["extracted"]
    c = ex["constraints"]
    return Profile(
        skills=set(ex["skills"]),
        tiles=set(intake_doc.get("category_ids", [])),
        budget=c.get("budget", "unknown"),
        can_move_away=c.get("can_move_away", "unknown"),
        hours_per_week=c.get("hours_per_week"),
        earned_before=c.get("earned_before", "unknown"),
        priority=c.get("priority", "unknown"),
        age=student.get("age"),
        district=student.get("district"),
    )


async def create(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    intake = await db["intake_sessions"].find_one({"user_id": user["_id"], "status": "done"}, sort=[("created_at", -1)])
    if intake is None or not intake.get("extracted"):
        raise ApiError(409, "intake_required", "Please finish the questions first.", "Answer the questions, then check what we understood.")
    student = await db["student_profiles"].find_one({"user_id": user["_id"]}) or {}
    profile = _profile_from(intake, student)
    ranked = rank(profile)
    paths = []
    for i, r in enumerate(ranked, 1):
        paths.append(
            {
                "rank": i,
                "career_id": r.career_id,
                "score": r.score,
                "factors": r.factors,
                "matched": r.matched,
                "related": r.related,
                "via": r.via,
                "tile": r.tile,
                "starter": r.starter,
                "tier": r.tier,
                "fits": r.fits,
                "priority_fit": r.priority_fit,
                "under18_theory_only": r.under18_theory_only,
                "reason": reasons.build_reason(r, profile.priority),
                "reason_source": {"en": "template", "hi": "template", "mr": "template"},
            }
        )
    doc = {
        "_id": uuid.uuid4().hex,
        "user_id": user["_id"],
        "intake_id": intake["_id"],
        "created_at": timeutil.utcnow(),
        "weights": WEIGHTS,
        "based_on": {"skills": ex_skills(intake), "learner_added": intake["extracted"].get("learner_added", []), "tiles": intake.get("category_ids", [])},
        "paths": paths,
        "enrichment": "pending",
        "priority": profile.priority,
    }
    await db["assessments"].insert_one(doc)
    return assessment_view(doc)


def ex_skills(intake: dict[str, Any]) -> list[str]:
    return list(intake["extracted"]["skills"])


async def latest(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["assessments"].find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
    if doc is None:
        raise ApiError(404, "no_assessment", "No paths yet.", "Finish the questions first.")
    return assessment_view(doc)


async def get(db: AsyncIOMotorDatabase, user: dict[str, Any], assessment_id: str) -> dict[str, Any]:
    doc = await db["assessments"].find_one({"_id": assessment_id, "user_id": user["_id"]})  # scoped to the caller here
    if doc is None:
        raise ApiError(404, "assessment_not_found", "We could not find those paths.", "Go back and ask for your paths again.")
    return assessment_view(doc)


# ---------------------------------------------------------------------------
# Optional AI-written reasons (never blocks, never overrides the guard)
# ---------------------------------------------------------------------------

REASON_SYSTEM = (
    "You write ONE short, plain sentence (under 30 words) saying why a career path may suit a young learner in rural "
    "Maharashtra, using only the facts given. Do not mention money, income, demand, numbers or promises. "
    'Output JSON only, in the form {"reason": "..."}.'
)
TRANSLATE_SYSTEM = (
    "Translate each English sentence into simple Hindi and into simple Marathi, in the same order. Keep the meaning exactly. "
    'Output JSON only, in the form {"hi": ["..."], "mr": ["..."]} with one entry per sentence.'
)


def _reason_prompt(path: dict[str, Any], age_band: str | None) -> str:
    career = catalog.career(path["career_id"])
    assert career is not None
    skill_names = {s["id"]: s["name"]["en"] for s in catalog.skills()}
    have = ", ".join(skill_names[s] for s in path["matched"] if s in skill_names) or "none yet"
    return (
        f"Career path: {career['name']['en']}\n"
        f"What it is: {career['summary']['en']}\n"
        f"Skills the learner already has that it uses: {have}\n"
        f"What the learner said matters most: {path.get('priority', 'unknown')}\n"
        f"Learner age band: {age_band or 'unknown'}\n"
        "Write the one sentence now."
    )


async def enrich(db: AsyncIOMotorDatabase, llm: LLMService, assessment_id: str, user_id: str) -> None:
    """Replace the top reasons with model-written ones where the model passes the guard. Failures change nothing."""
    doc = await db["assessments"].find_one({"_id": assessment_id, "user_id": user_id})
    if doc is None:
        return
    student = await db["student_profiles"].find_one({"user_id": user_id}, {"age_band": 1}) or {}
    updates: dict[str, Any] = {}
    chosen: list[tuple[int, str]] = []
    try:
        for idx, path in enumerate(doc["paths"][:ENRICH_TOP]):
            if path.get("starter"):
                continue  # a starting point keeps its honest template: we found no match to write about
            req = LLMRequest(
                task=Task.REASONING,
                system=REASON_SYSTEM,
                prompt=_reason_prompt({**path, "priority": doc.get("priority", "unknown")}, student.get("age_band")),
                schema=ReasonOut.model_json_schema(),
                temperature=0.3,
                prompt_version=REASON_VERSION,
            )
            result = await llm.generate(req, ReasonOut, fallback=lambda: ReasonOut(reason=""))
            if result.source != "fallback" and reasons.acceptable_reason(result.value.reason):
                chosen.append((idx, result.value.reason.strip()))
        if chosen:
            tr = await llm.generate(
                LLMRequest(
                    task=Task.TRANSLATION,
                    system=TRANSLATE_SYSTEM,
                    prompt="Sentences:\n" + "\n".join(f"{i + 1}. {text}" for i, (_, text) in enumerate(chosen)),
                    schema=ReasonTranslations.model_json_schema(),
                    temperature=0.0,
                    prompt_version=REASON_TRANSLATE_VERSION,
                ),
                ReasonTranslations,
                fallback=lambda: ReasonTranslations(),
            )
            ok = tr.source != "fallback" and len(tr.value.hi) == len(chosen) and len(tr.value.mr) == len(chosen)
            for n, (idx, text) in enumerate(chosen):
                updates[f"paths.{idx}.reason.en"] = text
                updates[f"paths.{idx}.reason_source.en"] = "ai"
                if ok and tr.value.hi[n].strip() and tr.value.mr[n].strip():
                    updates[f"paths.{idx}.reason.hi"] = tr.value.hi[n].strip()
                    updates[f"paths.{idx}.reason.mr"] = tr.value.mr[n].strip()
                    updates[f"paths.{idx}.reason_source.hi"] = "ai_translated"
                    updates[f"paths.{idx}.reason_source.mr"] = "ai_translated"
        updates["enrichment"] = "done"
    except Exception as exc:  # enrichment is a nicety; the baseline reasons stand
        log.warning("reason enrichment failed", extra={"error": type(exc).__name__})
        updates = {"enrichment": "failed"}
    await db["assessments"].update_one({"_id": assessment_id, "user_id": user_id}, {"$set": updates})


# ---------------------------------------------------------------------------
# Choosing a path
# ---------------------------------------------------------------------------


def journey_view(doc: dict[str, Any]) -> dict[str, Any]:
    career = catalog.career(doc["career_id"])
    return {
        "id": doc["_id"],
        "state": doc["state"],
        "career": career_card(career) if career else {"career_id": doc["career_id"]},
        "assessment_id": doc["assessment_id"],
        "created_at": timeutil.ensure_aware(doc["created_at"]),
    }


async def select_career(db: AsyncIOMotorDatabase, user: dict[str, Any], career_id: str) -> dict[str, Any]:
    if catalog.career(career_id) is None:
        raise ApiError(404, "career_not_found", "We could not find that career.", "Pick one from your list.")
    assessment = await db["assessments"].find_one({"user_id": user["_id"]}, sort=[("created_at", -1)])
    if assessment is None or career_id not in [p["career_id"] for p in shown_paths(assessment)]:
        raise ApiError(409, "not_in_paths", "That career is not one of your paths.", "Pick one from your list.")
    now = timeutil.utcnow()
    # One live journey per learner: choosing again replaces the earlier choice (progress on it is kept in history).
    # A finished path (completed, opportunities open, enrolled) is kept, so its opportunities and applications stay.
    live = {"student_id": user["_id"], "state": {"$nin": ["abandoned", "enrolled", "completed", "opportunities_open"]}}
    old_ids = [j["_id"] async for j in db["journeys"].find(live, {"_id": 1})]
    await db["journeys"].update_many(live, {"$set": {"state": "abandoned", "updated_at": now}})
    if old_ids:  # a mentor request for a path the learner dropped must not stay open
        await db["matches"].update_many({"journey_id": {"$in": old_ids}, "status": "pending"}, {"$set": {"status": "cancelled", "decided_at": now}})
    doc = {
        "_id": uuid.uuid4().hex,
        "student_id": user["_id"],
        "career_id": career_id,
        "assessment_id": assessment["_id"],
        "state": "path_selected",
        "teacher_id": None,
        "milestones": [],
        "created_at": now,
        "updated_at": now,
    }
    await db["journeys"].insert_one(doc)
    return journey_view(doc)


async def my_journey(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["journeys"].find_one({"student_id": user["_id"], "state": {"$ne": "abandoned"}}, sort=[("created_at", -1)])
    if doc is None:
        raise ApiError(404, "no_journey", "You have not picked a path yet.", "Pick one from your paths.")
    return journey_view(doc)
