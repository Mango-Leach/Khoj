"""Finishing a path, the top 3 opportunities, and applying (CLAUDE.md sections 6 and 9; milestone M8).

Finishing: when every milestone of the path is done (every live assignment has approved work, which needs a mentor),
the learner finishes the journey and it opens to opportunities. KHOJ does not certify anyone: a high-risk trade still
needs an in-person check by a qualified assessor, and the app says so.

Opportunities are real programmes, linked out. Plain code decides:
- eligibility, by the same rules engine as the scholarships (never a model);
- which ones are shown, by hard filters (a deadline that has passed, a language the programme does not use, a rule the
  learner definitely fails);
- the order, by a weighted score. The starting weights are the spec's: 0.40 fit with the learner's path, 0.25 how near,
  0.20 whether it pays (the stated kind of pay, never an amount), 0.15 source trust and recency.

KHOJ never applies for anyone. The learner applies on the official site, with a mentor's help if they have one, and
tells KHOJ what happened. Only the learner's own confirmation moves an application to `confirmed`.
"""
from __future__ import annotations

import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import timeutil
from app.config import Settings
from app.errors import ApiError
from app.services import assignments, catalog, events, journeys, notifications, rules_engine, schemes

OPEN_STATES = ("opportunities_open", "enrolled")
FINISHED_STATES = ("completed", "opportunities_open", "enrolled")
WEIGHTS = {"career_fit": 0.40, "proximity": 0.25, "income_clarity": 0.20, "trust_recency": 0.15}
TOP = 3
MORE_LIMIT = 10
# Before a learner finishes the path: how many they may see with 0, 1, 2 and 3 approved milestones.
# Two previews from the start, then more as a mentor approves work. The rest opens when they finish.
UNLOCK_SHOWN = (2, 3, 6, 6)
# How clearly the programme says it pays. Only the kind is known, never an amount.
INCOME_CLARITY = {"stipend": 1.0, "support": 0.6, "none": 0.3, "unknown": 0.2}
UNVERIFIED_TRUST = 0.6
MACHINE_TRANSLATED = ["hi", "mr"]

APPLICATION_NEXT: dict[str, frozenset[str]] = {
    "interested": frozenset({"applied", "withdrawn"}),
    "mentor_assisted": frozenset({"applied", "withdrawn"}),
    "applied": frozenset({"confirmed", "withdrawn"}),
    "confirmed": frozenset(),
    "withdrawn": frozenset({"interested"}),
}


# ---------------------------------------------------------------------------
# Finishing the path
# ---------------------------------------------------------------------------


async def complete(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> dict[str, Any]:
    """Finish the path once every milestone is done, then open it to opportunities. Asking twice changes nothing."""
    journey = await db["journeys"].find_one({"_id": journey_id, "student_id": user["_id"]})
    if journey is None or journey["state"] == "abandoned":
        raise ApiError(404, "journey_not_found", "We could not find that journey.", "Go back and try again.")
    career = catalog.career(journey["career_id"])
    hazardous = bool(career and career["safety"]["class"] == "high")
    if journey["state"] in FINISHED_STATES:
        return _completion(journey, hazardous)
    if journey["state"] not in ("in_progress", "stalled"):
        raise ApiError(409, "mentor_required", "Your mentor checks your work before you finish.", "Ask a mentor first. Your practice stays saved.")

    view = await assignments.milestones_view(db, user, journey_id)
    waiting = [m["key"] for m in view["milestones"] if m["state"] != "done"]
    if waiting:
        raise ApiError(409, "milestones_not_done", "There is still work to finish.", "Finish every step and get it approved first.")

    if journey["state"] == "stalled":
        await journeys.move(db, journey_id, "in_progress", expect="stalled")
    now = timeutil.utcnow()
    moved = await journeys.move(db, journey_id, "completed", expect="in_progress", completed_at=now)
    if moved is not None:
        moved = await journeys.move(db, journey_id, "opportunities_open", expect="completed", opportunities_open_at=now)
        student = await db["student_profiles"].find_one({"user_id": user["_id"]}, {"block": 1, "district": 1}) or {}
        await events.record(
            db, "journey_completed", user["_id"], ref=journey_id, block=student.get("block"), district=student.get("district"),
            skill_tags=[r["skill"] for r in (career or {}).get("required_skills", [])],
        )
        await notifications.notify(db, user["_id"], "path_complete", "/opportunities", dedupe_key=f"path_complete:{journey_id}")
    fresh = moved or await db["journeys"].find_one({"_id": journey_id}) or journey
    return _completion(fresh, hazardous)


def _completion(journey: dict[str, Any], hazardous: bool) -> dict[str, Any]:
    return {
        "journey_id": journey["_id"],
        "state": journey["state"],
        "career_id": journey["career_id"],
        # KHOJ never certifies work. A high-risk trade needs a qualified assessor to check it in person.
        "in_person_check_needed": hazardous,
    }


# ---------------------------------------------------------------------------
# Scoring (pure)
# ---------------------------------------------------------------------------


def rule_of(opp: dict[str, Any]) -> dict[str, Any]:
    """The rule record that decides eligibility: the linked scheme's file, or the record's own conditions."""
    if opp.get("scheme_id"):
        scheme = catalog.scheme(opp["scheme_id"])
        if scheme is not None:
            return scheme
    return opp


def career_fit(opp: dict[str, Any], career: dict[str, Any]) -> tuple[float, str] | None:
    """1 for a programme made for this path, a lower figure for one open to any path, and None when it has no link."""
    if career["career_id"] in opp.get("career_ids", []) or set(opp.get("route_ids", [])) & set(career.get("opportunity_routes", [])):
        return 1.0, "your_path"
    if opp.get("any_career"):
        return 0.4, "any_path"
    return None


def proximity(opp: dict[str, Any], district: str, state: str) -> tuple[float, str]:
    if opp.get("districts"):
        return (1.0, "in_district") if district in opp["districts"] else (0.2, "other_district")
    if opp["scope"] == "state":
        return (0.7, "in_state") if state == "maharashtra" else (0.0, "other_state")
    return 0.5, "anywhere"


def trust_recency(rule: dict[str, Any], today, max_days: int) -> float:
    """A record a person has verified counts for more, and any record counts for less as it gets older."""
    verified = rules_engine.parse_date(rule.get("verified_on"))
    basis = verified or rules_engine.parse_date(rule.get("entered_on"))
    if basis is None:
        return 0.0
    recency = max(0.0, 1.0 - (today - basis).days / max_days) if max_days > 0 else 0.0
    return round((1.0 if verified else UNVERIFIED_TRUST) * recency, 3)


def score(factors: dict[str, float]) -> float:
    return round(sum(WEIGHTS[k] * factors[k] for k in WEIGHTS), 4)


def _deadline_passed(opp: dict[str, Any], today) -> bool:
    deadline = rules_engine.parse_date(opp.get("deadline"))
    return deadline is not None and today > deadline


def _language_ok(opp: dict[str, Any], language: str) -> bool:
    langs = opp.get("languages") or []
    return not langs or language in langs or "en" in langs


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------


def _card(opp: dict[str, Any], result: dict[str, Any], total: float, factors: dict[str, float], reasons: list[str]) -> dict[str, Any]:
    return {
        "id": opp["id"],
        "kind": opp["kind"],
        "title": opp["title_i18n"],
        "summary": opp["summary_i18n"],
        "how": opp["how_i18n"],
        "scope": opp["scope"],
        "income": opp["income"],
        "apply_url": opp["apply_url"],
        "docs": result["docs"],
        "needs": result["needs"],
        "machine_translated": MACHINE_TRANSLATED,
        "score": total,
        "factors": factors,
        "reasons": reasons,
        "eligibility": {
            "status": result["status"],
            "passed": result["passed"],
            "failed": result["failed"],
            "missing": result["missing"],
            "unresolved": result["unresolved"],
            "opens_at": result["opens_at"],
            "stale": result["stale"],
            "expired": result["expired"],
        },
        "source": result["source"],
        "application": None,
    }


async def latest_finished(db: AsyncIOMotorDatabase, user: dict[str, Any], career_id: str | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"student_id": user["_id"], "state": {"$in": list(OPEN_STATES)}}
    if career_id:
        query["career_id"] = career_id
    journey = await db["journeys"].find_one(query, sort=[("created_at", -1)])
    if journey is None:
        raise ApiError(409, "not_completed", "Opportunities open when you finish your path.", "Finish your steps with your mentor first.")
    return journey


async def current_journey(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    """The learner's finished path if they have one, otherwise the path they are on now."""
    journey = await db["journeys"].find_one({"student_id": user["_id"], "state": {"$in": list(FINISHED_STATES)}}, sort=[("created_at", -1)])
    if journey is None:
        journey = await db["journeys"].find_one({"student_id": user["_id"], "state": {"$ne": "abandoned"}}, sort=[("created_at", -1)])
    if journey is None:
        raise ApiError(409, "no_path", "Pick a path to see opportunities.", "Choose a path first.")
    return journey


def shown_count(approved: int) -> int:
    """How many opportunities a learner may see before they finish the path, by approved milestones."""
    return UNLOCK_SHOWN[max(0, min(approved, len(UNLOCK_SHOWN) - 1))]


async def _applications(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["opportunity_id"]: {"id": a["_id"], "status": a["status"]} async for a in db["applications"].find({"student_id": user["_id"]})}


async def _compute(db: AsyncIOMotorDatabase, user: dict[str, Any], settings: Settings, given: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score every programme for the learner's path and apply what they may see so far.

    Only a mentor's approval moves a milestone to done, so only approved work unlocks more. The server holds back the
    rest: a hidden programme is never sent, not even its name."""
    journey = await current_journey(db, user)
    finished = journey["state"] in FINISHED_STATES
    career = catalog.career(journey["career_id"])
    if career is None:
        raise ApiError(404, "career_not_found", "We could not find that career.", "")
    student = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if student is None:
        raise ApiError(409, "profile_required", "Please finish your profile first.", "")
    facts = await schemes.profile_facts(db, user)
    facts.update(given or {})  # the learner's answers never replace age, class or state from the profile
    language = user.get("language", "en")
    today = timeutil.utcnow().date()

    ranked: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    not_yet: list[dict[str, Any]] = []
    for opp in catalog.opportunities():
        fit = career_fit(opp, career)
        if fit is None or _deadline_passed(opp, today) or not _language_ok(opp, language):
            continue
        rule = rule_of(opp)
        result = schemes.result_view(rule, facts, today, settings.verified_max_days)
        near, near_reason = proximity(opp, student["district"], str(student["state"]).lower())
        factors = {
            "career_fit": fit[0],
            "proximity": near,
            "income_clarity": INCOME_CLARITY[opp["income"]],
            "trust_recency": trust_recency(rule, today, settings.verified_max_days),
        }
        reasons = [fit[1], near_reason]
        if opp["income"] in ("stipend", "support"):
            reasons.append("pays_stipend" if opp["income"] == "stipend" else "gives_support")
        reasons.append("eligible" if result["status"] == rules_engine.ELIGIBLE else "check_office")
        card = _card(opp, result, score(factors), factors, reasons)
        if result["expired"]:
            expired.append(card)
        elif result["status"] == rules_engine.NOT_ELIGIBLE:
            not_yet.append(card)
        else:
            ranked.append(card)

    ranked.sort(key=lambda c: (-c["score"], schemes.STATUS_ORDER[c["eligibility"]["status"]], c["id"]))
    not_yet.sort(key=lambda c: (-c["score"], c["id"]))
    apps = await _applications(db, user)
    for card in ranked + expired + not_yet:
        card["application"] = apps.get(card["id"])

    total = len(assignments.MILESTONES)
    if finished:
        approved, visible, locked = total, ranked[:TOP + MORE_LIMIT], 0
    else:
        view = await assignments.milestones_view(db, user, journey["_id"])
        approved = sum(1 for m in view["milestones"] if m["state"] == "done")
        visible = ranked[: shown_count(approved)]
        locked = len(ranked) - len(visible)
        expired, not_yet = [], []  # these wait until the path is finished
    waiting = {m["fact"] for c in visible for m in c["eligibility"]["missing"] if c["eligibility"]["status"] == rules_engine.CHECK}
    return {
        "journey": {"id": journey["_id"], "state": journey["state"], "career_id": journey["career_id"]},
        "top": visible[:TOP],
        "more": visible[TOP:] + expired,
        "not_yet": not_yet,
        "ask": [f for f in schemes.ASK_ORDER if f in waiting],
        "weights": WEIGHTS,
        "in_person_check_needed": career["safety"]["class"] == "high",
        "unlock": {"finished": finished, "approved": approved, "total": total, "locked": locked, "has_mentor": assignments.has_mentor(journey)},
        "visible_ids": [c["id"] for c in visible],
    }


async def listing(db: AsyncIOMotorDatabase, user: dict[str, Any], settings: Settings, given: dict[str, Any] | None = None) -> dict[str, Any]:
    out = await _compute(db, user, settings, given)
    out.pop("visible_ids")
    return out


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


def application_view(doc: dict[str, Any], opp: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {
        "id": doc["_id"],
        "opportunity_id": doc["opportunity_id"],
        "status": doc["status"],
        "mentor_helped": doc.get("assisted_by") is not None,
        "created_at": timeutil.ensure_aware(doc["created_at"]),
        "updated_at": timeutil.ensure_aware(doc["updated_at"]),
    }
    if opp is not None:
        out.update({"title": opp["title_i18n"], "apply_url": opp["apply_url"], "kind": opp["kind"]})
    return out


async def _definitely_not_eligible(db: AsyncIOMotorDatabase, user: dict[str, Any], opp: dict[str, Any], settings: Settings) -> bool:
    facts = await schemes.profile_facts(db, user)
    result = rules_engine.evaluate(rule_of(opp), facts, timeutil.utcnow().date(), settings.verified_max_days)
    return result["status"] == rules_engine.NOT_ELIGIBLE


async def apply(db: AsyncIOMotorDatabase, user: dict[str, Any], opportunity_id: str, settings: Settings) -> dict[str, Any]:
    """The learner says they want this one. It is only a record of interest: they apply on the official site."""
    opp = catalog.opportunity(opportunity_id)
    if opp is None:
        raise ApiError(404, "opportunity_not_found", "We could not find that opportunity.", "")
    state = await _compute(db, user, settings)
    if not state["unlock"]["finished"] and opportunity_id not in state["visible_ids"]:
        raise ApiError(409, "opp_locked", "Finish more steps to open this one.", "Your mentor approves each step.")
    journey = await db["journeys"].find_one({"_id": state["journey"]["id"]}) or {}
    existing = await db["applications"].find_one({"student_id": user["_id"], "opportunity_id": opportunity_id})
    now = timeutil.utcnow()
    if existing is not None:
        if existing["status"] != "withdrawn":
            return application_view(existing, opp)  # asking twice is one request
        reopened = await db["applications"].find_one_and_update(
            {"_id": existing["_id"], "status": "withdrawn"},
            {"$set": {"status": "interested", "updated_at": now}, "$push": {"history": {"status": "interested", "at": now, "by": "student"}}},
            return_document=ReturnDocument.AFTER,
        )
        return application_view(reopened or existing, opp)
    if await _definitely_not_eligible(db, user, opp, settings):
        raise ApiError(409, "not_eligible", "You do not meet this programme's rules yet.", "See when it opens for you.")
    doc = {
        "_id": uuid.uuid4().hex,
        "student_id": user["_id"],
        "journey_id": journey["_id"],
        "opportunity_id": opportunity_id,
        "status": "interested",
        "assisted_by": None,
        "history": [{"status": "interested", "at": now, "by": "student"}],
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db["applications"].insert_one(doc)
    except DuplicateKeyError:  # two taps at once
        doc = await db["applications"].find_one({"student_id": user["_id"], "opportunity_id": opportunity_id}) or doc
        return application_view(doc, opp)
    await events.record(db, "opportunity_interest", user["_id"], ref=opportunity_id)
    if journey.get("teacher_id"):
        await notifications.notify(db, journey["teacher_id"], "help_apply", "/t/students", dedupe_key=f"help_apply:{doc['_id']}")
    return application_view(doc, opp)


async def my_applications(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    items = [application_view(a, catalog.opportunity(a["opportunity_id"])) async for a in db["applications"].find({"student_id": user["_id"]}).sort("updated_at", -1)]
    return {"applications": items}


async def update_status(db: AsyncIOMotorDatabase, user: dict[str, Any], application_id: str, status: str) -> dict[str, Any]:
    """The learner moves their own application: applied, confirmed (they heard back) or withdrawn.

    A mentor cannot confirm for them, and neither can KHOJ: only the learner's own word moves it to `confirmed`."""
    doc = await db["applications"].find_one({"_id": application_id, "student_id": user["_id"]})  # scoped to the caller here
    if doc is None:
        raise ApiError(404, "application_not_found", "We could not find that application.", "")
    opp = catalog.opportunity(doc["opportunity_id"])
    if doc["status"] == status:
        return application_view(doc, opp)
    if status not in APPLICATION_NEXT.get(doc["status"], frozenset()):
        raise ApiError(409, "bad_step", "That is not the next step.", "Follow the steps in order.")
    now = timeutil.utcnow()
    updated = await db["applications"].find_one_and_update(
        {"_id": application_id, "status": doc["status"]},
        {"$set": {"status": status, "updated_at": now}, "$push": {"history": {"status": status, "at": now, "by": "student"}}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise ApiError(409, "bad_step", "That is not the next step.", "Reload and try again.")
    await events.record(db, f"application_{status}", user["_id"], ref=doc["opportunity_id"])
    if status == "confirmed":
        await journeys.move(db, doc["journey_id"], "enrolled", expect="opportunities_open")
    return application_view(updated, opp)


# ---------------------------------------------------------------------------
# The mentor's side
# ---------------------------------------------------------------------------


async def _mentor_journey_ids(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> list[str]:
    live = ["in_progress", "stalled", *FINISHED_STATES]  # a mentor can help a learner who is still on the path
    return [j["_id"] async for j in db["journeys"].find({"teacher_id": user["_id"], "state": {"$in": live}}, {"_id": 1})]


async def teacher_applications(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    """Learners of this mentor who want help applying."""
    ids = await _mentor_journey_ids(db, user)
    items = []
    async for a in db["applications"].find({"journey_id": {"$in": ids}, "status": {"$in": ["interested", "mentor_assisted"]}}).sort("created_at", 1):
        profile = await db["student_profiles"].find_one({"user_id": a["student_id"]}) or {}
        items.append({**application_view(a, catalog.opportunity(a["opportunity_id"])), "student": {"name": profile.get("name", ""), "age_band": profile.get("age_band")}})
    return {"applications": items}


async def assist(db: AsyncIOMotorDatabase, user: dict[str, Any], application_id: str) -> dict[str, Any]:
    """The mentor says they helped the learner prepare. This never applies for them and never confirms."""
    doc = await db["applications"].find_one({"_id": application_id})
    journey = await db["journeys"].find_one({"_id": doc["journey_id"]}) if doc else None
    if doc is None or journey is None or journey.get("teacher_id") != user["_id"]:
        raise ApiError(404, "application_not_found", "We could not find that application.", "")
    opp = catalog.opportunity(doc["opportunity_id"])
    if doc["status"] == "mentor_assisted":
        return application_view(doc, opp)
    if doc["status"] != "interested":
        raise ApiError(409, "bad_step", "This learner has already moved on.", "")
    now = timeutil.utcnow()
    updated = await db["applications"].find_one_and_update(
        {"_id": application_id, "status": "interested"},
        {"$set": {"status": "mentor_assisted", "assisted_by": user["_id"], "updated_at": now}, "$push": {"history": {"status": "mentor_assisted", "at": now, "by": "mentor"}}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise ApiError(409, "bad_step", "This learner has already moved on.", "")
    await events.record(db, "application_mentor_assisted", user["_id"], ref=doc["opportunity_id"])
    await notifications.notify(db, doc["student_id"], "mentor_helped", "/opportunities", dedupe_key=f"mentor_helped:{application_id}")
    return application_view(updated, opp)
