"""Milestones and assignments (CLAUDE.md section 6, steps 9 to 11, and the assignment lifecycle in section 10).

A journey has three milestones, the first three rungs of the career's ladder: explore, learn, practise. Each starts
with one default assignment built from the career card, so a learner can practise at once without a mentor. A mentor
may then ask the AI for more, edit a draft, and approve it before any learner sees it. The AI only drafts: a draft
reaches a learner only after a person approves it, and a draft that makes a money claim or (on a hazardous trade)
tells the learner to power something up is dropped before the mentor even sees it.

Everything is read through the caller's own user id in this layer, never trusted from the client.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app import timeutil
from app.errors import ApiError
from app.models.assignments import AssignmentIn, AssignmentPatch
from app.services import assessments, catalog, events
from app.services.llm import LLMRequest, LLMService, LLMUnavailable, Task

log = logging.getLogger("khoj.assignments")

MILESTONES = ("explore", "learn", "practise")
MAX_PER_MILESTONE = 6  # live (draft or approved) assignments per milestone
MAX_AI_DRAFTS = 3
PROMPT_VERSION = "assignment-draft-v1"
# the learner is with a mentor in these states; before that the work is saved practice
WITH_MENTOR = ("in_progress", "stalled")
LANGS = ("en", "hi", "mr")

# What every default assignment is scored on. Hindi and Marathi are DRAFTS for native-speaker review.
DEFAULT_CRITERIA: list[dict[str, str]] = [
    {"en": "Did the task as described", "hi": "काम बताए अनुसार किया", "mr": "काम सांगितल्याप्रमाणे केले"},
    {"en": "The work is clear and careful", "hi": "काम साफ़ और ध्यान से किया है", "mr": "काम स्वच्छ आणि काळजीपूर्वक केले आहे"},
    {"en": "Explains what was done and what to improve", "hi": "बताया कि क्या किया और क्या सुधारना है", "mr": "काय केले आणि काय सुधारायचे ते सांगितले"},
]
HOW_TO_SHOW = {
    "en": "Show your work with a short written answer, and up to 3 photos if you can.",
    "hi": "अपना काम एक छोटे लिखित जवाब से दिखाइए, और हो सके तो 3 तक फ़ोटो भी जोड़िए।",
    "mr": "तुमचं काम एका छोट्या लिखित उत्तराने दाखवा, आणि जमलं तर 3 पर्यंत फोटो जोडा.",
}
SAFETY_LINE = {
    "en": "Safety: practise on a training board or with the power off and unplugged. Never switch on, or touch, live wiring or a running motor.",
    "hi": "सुरक्षा: ट्रेनिंग बोर्ड पर या बिजली बंद और प्लग निकालकर अभ्यास कीजिए। चालू तार या चलती मोटर को कभी चालू या स्पर्श न करें।",
    "mr": "सुरक्षितता: ट्रेनिंग बोर्डवर किंवा वीज बंद करून आणि प्लग काढून सराव करा. चालू वायरिंगला किंवा चालू मोटरला कधीही चालू करू नका किंवा हात लावू नका.",
}


def pick(text: dict[str, str], lang: str = "en") -> str:
    """The text in the wanted language, else English, else whatever exists."""
    return text.get(lang) or text.get("en") or next(iter(text.values()), "")


# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------


async def journey_access(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> tuple[dict[str, Any], str]:
    """The journey and the caller's side of it: the learner, or the mentor of a journey in progress. Anyone else gets a 404."""
    journey = await db["journeys"].find_one({"_id": journey_id})
    if journey is not None:
        if journey["student_id"] == user["_id"]:
            return journey, "student"
        if journey.get("teacher_id") == user["_id"] and journey["state"] in WITH_MENTOR:
            return journey, "teacher"
    raise ApiError(404, "journey_not_found", "We could not find that journey.", "Go back and try again.")


def has_mentor(journey: dict[str, Any]) -> bool:
    return bool(journey.get("teacher_id")) and journey["state"] in WITH_MENTOR


def _career_of(journey: dict[str, Any]) -> dict[str, Any]:
    career = catalog.career(journey["career_id"])
    if career is None:
        raise ApiError(404, "career_not_found", "We could not find that career.", "")
    return career


def _hazardous(career: dict[str, Any]) -> bool:
    return career["safety"]["class"] == "high"


# ---------------------------------------------------------------------------
# Default assignments, one per milestone, from the career card
# ---------------------------------------------------------------------------


def _rung(career: dict[str, Any], key: str) -> dict[str, Any]:
    return next(r for r in assessments.career_detail(career)["ladder"] if r["key"] == key)


def template_fields(career: dict[str, Any], key: str) -> dict[str, Any]:
    rung = _rung(career, key)
    title = {lang: rung["title"][lang] for lang in LANGS if lang in rung["title"]}
    instructions: dict[str, str] = {}
    for lang in LANGS:
        if lang not in rung["detail"]:
            continue
        text = f"{rung['detail'][lang]} {HOW_TO_SHOW[lang]}"
        if _hazardous(career):
            text += f" {SAFETY_LINE[lang]}"
        instructions[lang] = text
    return {
        "title": title,
        "instructions": instructions,
        "criteria": [{"id": f"c{i}", "text": dict(c)} for i, c in enumerate(DEFAULT_CRITERIA, 1)],
    }


async def ensure_templates(db: AsyncIOMotorDatabase, journey: dict[str, Any]) -> None:
    """Create the default assignment of each milestone once. The id is fixed, so a race or a retry makes no duplicate."""
    career = _career_of(journey)
    now = timeutil.utcnow()
    for key in MILESTONES:
        doc = {
            "_id": f"{journey['_id']}:{key}:template",
            "journey_id": journey["_id"],
            "student_id": journey["student_id"],
            "milestone": key,
            **template_fields(career, key),
            "source": "template",
            "status": "approved",
            "created_by": None,
            "approved_by": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await db["assignments"].insert_one(doc)
        except DuplicateKeyError:
            pass


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def assignment_view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "journey_id": doc["journey_id"],
        "milestone": doc["milestone"],
        "title": doc["title"],
        "instructions": doc["instructions"],
        "criteria": doc["criteria"],
        "source": doc["source"],
        "status": doc["status"],
    }


async def milestones_view(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str) -> dict[str, Any]:
    journey, who = await journey_access(db, user, journey_id)
    if journey["state"] == "abandoned":
        raise ApiError(404, "journey_not_found", "We could not find that journey.", "Go back and try again.")
    await ensure_templates(db, journey)
    career = _career_of(journey)
    statuses = ["approved"] if who == "student" else ["approved", "draft"]
    assignments = [a async for a in db["assignments"].find({"journey_id": journey_id, "status": {"$in": statuses}}).sort("created_at", 1)]
    latest: dict[str, dict[str, Any]] = {}
    approved: set[str] = set()
    async for s in db["submissions"].find({"journey_id": journey_id}).sort("attempt", 1):
        latest[s["assignment_id"]] = s  # ascending, so the last one wins
        if s["status"] == "approved":
            approved.add(s["assignment_id"])
    waiting = 0
    out = []
    for key in MILESTONES:
        rung = _rung(career, key)
        items = []
        for a in (x for x in assignments if x["milestone"] == key):
            sub = latest.get(a["_id"])
            if sub and sub["status"] == "submitted":
                waiting += 1
            items.append(
                {
                    "id": a["_id"],
                    "title": a["title"],
                    "source": a["source"],
                    "status": a["status"],
                    "approved": a["_id"] in approved,
                    "submission": {"id": sub["_id"], "attempt": sub["attempt"], "status": sub["status"], "call_needed": bool((sub.get("review") or {}).get("call_needed"))} if sub else None,
                }
            )
        live = [i for i in items if i["status"] == "approved"]
        done = sum(1 for i in live if i["approved"])
        out.append(
            {
                "key": key,
                "title": rung["title"],
                "detail": rung["detail"],
                "assignments": items,
                "done": done,
                "total": len(live),
                "state": "done" if live and done == len(live) else "active" if any(i["submission"] for i in items) else "open",
            }
        )
    return {
        "journey_id": journey_id,
        "career": assessments.career_card(career),
        "journey_state": journey["state"],
        "has_mentor": has_mentor(journey),
        "side": who,
        "waiting": waiting,
        "milestones": out,
    }


async def get_assignment(db: AsyncIOMotorDatabase, user: dict[str, Any], assignment_id: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    """The assignment, its journey and the caller's side. A learner never sees a draft or a retired assignment."""
    doc = await db["assignments"].find_one({"_id": assignment_id})
    if doc is None:
        raise ApiError(404, "assignment_not_found", "We could not find that assignment.", "")
    journey, who = await journey_access(db, user, doc["journey_id"])
    if who == "student" and doc["status"] != "approved":
        raise ApiError(404, "assignment_not_found", "We could not find that assignment.", "")
    if who == "teacher" and doc["status"] == "retired":
        raise ApiError(404, "assignment_not_found", "We could not find that assignment.", "")
    return doc, journey, who


# ---------------------------------------------------------------------------
# AI drafts (a mentor asks, a mentor approves)
# ---------------------------------------------------------------------------


class DraftItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=3, max_length=100)
    instructions: str = Field(min_length=20, max_length=900)
    criteria: list[str] = Field(min_length=3, max_length=5)


class DraftOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    assignments: list[DraftItem] = Field(min_length=1, max_length=MAX_AI_DRAFTS)


SYSTEM = (
    "You draft practice assignments for a young learner in rural Maharashtra who is learning a trade or skill, for their "
    "mentor to review and edit. Use only the facts given. Write plain, short English.\n"
    "Each assignment has: a title (under 8 words); instructions (2 to 4 short sentences saying exactly what to do and what "
    "to show, a short written answer and optionally up to 3 photos); and 3 to 5 short criteria a mentor can score from 1 to 4.\n"
    "Never mention money, prices, income or earnings. Never include links. Never ask for names, phone numbers or addresses.\n"
    "For a hazardous trade (electrical work, motors) the learner practises only on a training board or with the power off "
    "and unplugged. Never tell the learner to switch on, energise, plug in or touch live wiring, or to run a motor.\n"
    'Answer with JSON only, in this shape: {"assignments": [{"title": <short title>, "instructions": <what to do and show>, '
    '"criteria": [<check 1>, <check 2>, <check 3>]}]}. Write real sentences. Never answer with dots or a placeholder.'
)

_MONEY = re.compile(r"₹|\brs\.?\s*\d|\brupee|\bincome\b|\bsalary\b|\bearn(?:s|ing|ings)?\b|https?://|www\.", re.IGNORECASE)
_POWER = re.compile(
    r"switch(?:ed|ing)?\s+on|turn(?:ed|ing)?\s+on|power(?:ed|ing)?\s+(?:on|up)|energi[sz]e|plug(?:ged|ging)?\s+in|live\s+(?:wire|wiring|circuit|supply)|mains|start\s+the\s+motor|run\s+the\s+motor",
    re.IGNORECASE,
)


_WORD = re.compile(r"[^\W\d_]{3,}")  # a run of letters (any script), so "..." or "---" is not text


def has_words(text: str) -> bool:
    return _WORD.search(text) is not None


def acceptable_draft(item: DraftItem, hazardous: bool) -> bool:
    """A draft is shown to the mentor only if it is real text, makes no money claim and, on a hazardous trade, never tells a learner to power anything up."""
    if not all(has_words(t) for t in (item.title, item.instructions, *item.criteria)):
        return False  # a small model sometimes copies a placeholder such as "..." from the prompt
    text = " ".join([item.title, item.instructions, *item.criteria])
    if _MONEY.search(text):
        return False
    if hazardous and _POWER.search(text):
        return False
    return all(3 <= len(c.strip()) <= 140 for c in item.criteria)


def _checked_model(hazardous: bool) -> type[DraftOut]:
    """The output model with our rules inside it. An answer that breaks them is retried, tried on the other provider, and
    never cached, so asking again can give a better one. Unacceptable items are dropped; none left means the answer fails."""

    class Checked(DraftOut):
        @model_validator(mode="after")
        def _keep_acceptable(self) -> "Checked":
            kept = [i for i in self.assignments if acceptable_draft(i, hazardous)]
            if not kept:
                raise ValueError("no acceptable assignment")
            self.assignments = kept
            return self

    Checked.__name__ = "DraftOutHazard" if hazardous else "DraftOut"  # part of the cache key
    return Checked


def _norm(title: str) -> str:
    return re.sub(r"\W+", " ", title).strip().casefold()


def _draft_prompt(career: dict[str, Any], key: str, journey: dict[str, Any], student: dict[str, Any], existing: list[str]) -> str:
    skill_names = {s["id"]: s["name"]["en"] for s in catalog.skills()}
    skills = ", ".join(skill_names.get(r["skill"], r["skill"]) for r in career["required_skills"])
    rung = _rung(career, key)
    return (
        f"Career path: {career['name']['en']}\n"
        f"What it is: {career['summary']['en']}\n"
        f"Skills it uses: {skills}\n"
        f"Safety class: {career['safety']['class']}\n"
        f"Milestone: {rung['title']['en']} - {rung['detail']['en']}\n"
        f"Learner age band: {student.get('age_band') or 'unknown'}\n"
        f"Assignments that already exist for this milestone (do not repeat them): {'; '.join(existing) or 'none'}\n"
        f"Write {MAX_AI_DRAFTS} different assignments now."
    )


def _new_doc(journey: dict[str, Any], key: str, lang: str, title: str, instructions: str, criteria: list[str], source: str, by: str | None) -> dict[str, Any]:
    now = timeutil.utcnow()
    return {
        "_id": uuid.uuid4().hex,
        "journey_id": journey["_id"],
        "student_id": journey["student_id"],
        "milestone": key,
        "title": {lang: title},
        "instructions": {lang: instructions},
        "criteria": [{"id": f"c{i}", "text": {lang: c}} for i, c in enumerate(criteria, 1)],
        "source": source,
        "status": "draft",
        "created_by": by,
        "approved_by": None,
        "created_at": now,
        "updated_at": now,
    }


async def _teacher_context(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str, key: str) -> dict[str, Any]:
    if key not in MILESTONES:
        raise ApiError(404, "milestone_not_found", "We could not find that milestone.", "")
    journey, who = await journey_access(db, user, journey_id)
    if who != "teacher":
        raise ApiError(403, "mentor_only", "Only the mentor can do this.", "")
    await ensure_templates(db, journey)
    return journey


async def _live_titles(db: AsyncIOMotorDatabase, journey_id: str, key: str) -> list[dict[str, Any]]:
    return [a async for a in db["assignments"].find({"journey_id": journey_id, "milestone": key, "status": {"$in": ["approved", "draft"]}})]


async def draft_with_ai(db: AsyncIOMotorDatabase, llm: LLMService, user: dict[str, Any], journey_id: str, key: str) -> list[dict[str, Any]]:
    journey = await _teacher_context(db, user, journey_id, key)
    career = _career_of(journey)
    live = await _live_titles(db, journey_id, key)
    room = MAX_PER_MILESTONE - len(live)
    if room <= 0:
        raise ApiError(409, "too_many_assignments", "This milestone already has the most assignments.", "Retire one first.")
    student = await db["student_profiles"].find_one({"user_id": journey["student_id"]}, {"age_band": 1}) or {}  # age band only
    existing = [pick(a["title"]) for a in live]
    req = LLMRequest(
        task=Task.DRAFTING,
        system=SYSTEM,
        prompt=_draft_prompt(career, key, journey, student, existing),
        schema=DraftOut.model_json_schema(),
        temperature=0.5,
        prompt_version=PROMPT_VERSION,
    )
    try:
        result = await llm.generate(req, _checked_model(_hazardous(career)))
    except LLMUnavailable:
        raise ApiError(503, "ai_unavailable", "The AI helper could not give a usable draft right now.", "Try again, or write an assignment yourself.") from None
    taken = {_norm(pick(a["title"])) for a in live}
    fresh = []
    for item in result.value.assignments:
        if len(fresh) >= room or _norm(item.title) in taken:
            continue
        taken.add(_norm(item.title))
        fresh.append(_new_doc(journey, key, "en", item.title, item.instructions, [c.strip() for c in item.criteria], "ai", user["_id"]))
    if not fresh:
        raise ApiError(502, "ai_draft_rejected", "The AI only repeated what is already there.", "Try again, or write an assignment yourself.")
    await db["assignments"].insert_many(fresh)
    await events.record(db, "assignments_drafted", user["_id"], ref=journey_id, skill_tags=[r["skill"] for r in career["required_skills"]])
    return [assignment_view(d) for d in fresh]


async def create_manual(db: AsyncIOMotorDatabase, user: dict[str, Any], journey_id: str, key: str, body: AssignmentIn) -> dict[str, Any]:
    journey = await _teacher_context(db, user, journey_id, key)
    if len(await _live_titles(db, journey_id, key)) >= MAX_PER_MILESTONE:
        raise ApiError(409, "too_many_assignments", "This milestone already has the most assignments.", "Retire one first.")
    doc = _new_doc(journey, key, body.lang, body.title, body.instructions, body.criteria, "teacher", user["_id"])
    await db["assignments"].insert_one(doc)
    return assignment_view(doc)


async def patch(db: AsyncIOMotorDatabase, user: dict[str, Any], assignment_id: str, body: AssignmentPatch) -> dict[str, Any]:
    doc = await db["assignments"].find_one({"_id": assignment_id})
    if doc is None:
        raise ApiError(404, "assignment_not_found", "We could not find that assignment.", "")
    _, who = await journey_access(db, user, doc["journey_id"])
    if who != "teacher" or doc["status"] == "retired":
        raise ApiError(404, "assignment_not_found", "We could not find that assignment.", "")
    changes: dict[str, Any] = {}
    content = body.title is not None or body.instructions is not None or body.criteria is not None
    if content:
        if doc["status"] != "draft":
            raise ApiError(409, "assignment_locked", "Only a draft can be edited.", "Retire this one and write a new one.")
        lang = body.lang
        if body.title is not None:
            changes["title"] = {**doc["title"], lang: body.title}
        if body.instructions is not None:
            changes["instructions"] = {**doc["instructions"], lang: body.instructions}
        if body.criteria is not None:
            old = doc["criteria"]
            if len(body.criteria) == len(old):  # same checks, reworded in this language
                changes["criteria"] = [{"id": c["id"], "text": {**c["text"], lang: t}} for c, t in zip(old, body.criteria)]
            else:  # a different set of checks: start again in this language
                changes["criteria"] = [{"id": f"c{i}", "text": {lang: t}} for i, t in enumerate(body.criteria, 1)]
    if body.status == "approved":
        if doc["status"] != "draft":
            raise ApiError(409, "already_approved", "This assignment is already approved.", "")
        changes.update(status="approved", approved_by=user["_id"], approved_at=timeutil.utcnow())
    elif body.status == "retired":
        changes["status"] = "retired"
    if not changes:
        return assignment_view(doc)
    changes["updated_at"] = timeutil.utcnow()
    # the status in the filter keeps a double click or a retry from approving twice
    updated = await db["assignments"].find_one_and_update({"_id": assignment_id, "status": doc["status"]}, {"$set": changes}, return_document=ReturnDocument.AFTER)
    if updated is None:
        raise ApiError(409, "assignment_changed", "This assignment was just changed.", "Open it again.")
    return assignment_view(updated)
