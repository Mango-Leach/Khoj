"""Voice intake: confirmed answers in, a validated profile out.

Flow (CLAUDE.md section 6, steps 3 to 5):
  answer in the learner's language -> learner confirms the transcript (answer saved at once)
  -> on completion: translate pending answers to English in parallel, then extract skills,
     interests and constraints as schema-checked JSON
  -> the learner reviews and accepts.

Every AI step has a rule-based fallback, so a dead provider never blocks a learner.
Constraints (hours, travel, budget) come from tapped choices, never from a model's guess.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError

from app import timeutil
from app.errors import ApiError
from app.models.intake import (
    AcceptIn,
    ConfirmIn,
    Constraints,
    Extracted,
    LLMExtraction,
    SessionCreate,
    Translation,
)
from app.services import catalog, evidence
from app.services.llm import LLMRequest, LLMService, Task
from app.services.privacy import scrub_text

log = logging.getLogger("khoj.intake")

MIN_ANSWERS = 4  # enough signal to extract from; the screen asks all seven
EXTRACT_VERSION = "extract-v2"
TRANSLATE_VERSION = "translate-v1"
LANGUAGE_NAME = {"en": "English", "hi": "Hindi", "mr": "Marathi"}

EXTRACT_SYSTEM = (
    "You read a rural learner's short answers and fill in a small JSON profile. "
    "Use only what the learner actually said. Never invent a skill. "
    "Ignore personal names, phone numbers and places; never repeat them. "
    "Output JSON only."
)
TRANSLATE_SYSTEM = (
    "You translate a learner's words into plain, simple English for a career guidance app. "
    "Keep the meaning exactly. Do not add or remove facts. Leave personal names as they are. "
    'Output JSON only, in the form {"english": "..."}.'
)


def _not_found() -> ApiError:
    return ApiError(404, "session_not_found", "That intake session was not found.", "Start again from the skills screen.")


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _next_question_id(doc: dict[str, Any]) -> str | None:
    answered = {a["question_id"] for a in doc.get("answers", [])}
    return next((q["id"] for q in catalog.questions() if q["id"] not in answered), None)


def session_view(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["_id"],
        "status": doc["status"],
        "category_ids": doc.get("category_ids", []),
        "not_sure": doc.get("not_sure", False),
        "language": doc.get("language", "en"),
        "answers": [
            {
                "question_id": a["question_id"],
                "transcript": a["transcript_native"],
                "transcript_en": a["transcript_en"],
                "translation": a["translation"],
                "source": a["source"],
                "choice_id": a.get("choice_id"),
            }
            for a in doc.get("answers", [])
        ],
        "next_question_id": _next_question_id(doc),
        "total_questions": len(catalog.questions()),
        "extracted": doc.get("extracted"),
        "extraction_source": doc.get("extraction_source"),
        "created_at": timeutil.ensure_aware(doc["created_at"]),
        "updated_at": timeutil.ensure_aware(doc["updated_at"]),
    }


async def _own_session(db: AsyncIOMotorDatabase, user: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Every read is scoped to the caller here, in the API layer, never in the client."""
    doc = await db["intake_sessions"].find_one({"_id": session_id, "user_id": user["_id"]})
    if doc is None:
        raise _not_found()
    return doc


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def create_session(db: AsyncIOMotorDatabase, user: dict[str, Any], body: SessionCreate) -> dict[str, Any]:
    unknown = [c for c in body.category_ids if c not in catalog.category_ids()]
    if unknown:
        raise ApiError(422, "unknown_category", "One of those skills is not on the list.", "Choose from the pictures shown.")
    now = timeutil.utcnow()
    # One live session per learner: starting again abandons the old one.
    await db["intake_sessions"].update_many(
        {"user_id": user["_id"], "status": {"$in": ["in_progress", "review"]}},
        {"$set": {"status": "abandoned", "updated_at": now}},
    )
    doc = {
        "_id": uuid.uuid4().hex,
        "user_id": user["_id"],
        "category_ids": [] if body.not_sure else body.category_ids,
        "not_sure": body.not_sure,
        "language": body.language,
        "answers": [],
        "status": "in_progress",
        "extracted": None,
        "extraction_source": None,
        "created_at": now,
        "updated_at": now,
    }
    await db["intake_sessions"].insert_one(doc)
    return session_view(doc)


async def get_session(db: AsyncIOMotorDatabase, user: dict[str, Any], session_id: str) -> dict[str, Any]:
    return session_view(await _own_session(db, user, session_id))


async def latest_session(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["intake_sessions"].find_one(
        {"user_id": user["_id"], "status": {"$ne": "abandoned"}}, sort=[("created_at", -1)]
    )
    if doc is None:
        raise ApiError(404, "no_intake", "No intake yet.", "Start from the skills screen.")
    return session_view(doc)


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------


async def _to_english(llm: LLMService, text: str, language: str) -> tuple[str, str]:
    """Returns (english, status). A failed translation keeps the original, marked, never hidden."""
    if language == "en":
        return text, "not_needed"
    req = LLMRequest(
        task=Task.TRANSLATION,
        system=TRANSLATE_SYSTEM,
        prompt=f"Language: {LANGUAGE_NAME[language]}\nText: {text}",
        schema=Translation.model_json_schema(),
        temperature=0.0,
        prompt_version=TRANSLATE_VERSION,
    )
    result = await llm.generate(req, Translation, fallback=lambda: Translation(english=text))
    return scrub_text(result.value.english), ("failed" if result.source == "fallback" else "ok")


async def confirm_answer(
    db: AsyncIOMotorDatabase, llm: LLMService, user: dict[str, Any], session_id: str, body: ConfirmIn
) -> dict[str, Any]:
    doc = await _own_session(db, user, session_id)
    if doc["status"] != "in_progress":
        raise ApiError(409, "session_closed", "This intake is already finished.", "Start a new one.")
    q = catalog.question(body.question_id)
    if q is None:
        raise ApiError(422, "unknown_question", "That question does not exist.", "")

    if q["kind"] == "choice":
        choice = next((c for c in q["choices"] if c["id"] == body.choice_id), None)
        if choice is None:
            raise ApiError(422, "choice_required", "Please tap one of the answers.", "Choose one option.")
        native = choice["label"][body.language]
        english = choice["label"]["en"]
        translation, source = "not_needed", "tap"
    else:
        if body.choice_id is not None:
            raise ApiError(422, "unexpected_choice", "This question is answered in words.", "")
        native = scrub_text(body.transcript)
        if len(native) < 2:
            raise ApiError(422, "empty_answer", "Please say or type your answer.", "A few words are enough.")
        # Translation is slow and uneven (2 to 40 s on a free Gemini tier), so it is not done here:
        # the learner moves on at once and `complete` translates every pending answer in parallel.
        english, translation = ("", "pending") if body.language != "en" else (native, "not_needed")
        source = body.source
        choice = None

    entry = {
        "question_id": body.question_id,
        "transcript_native": native,
        "transcript_en": english,
        "translation": translation,
        "source": source,
        "choice_id": body.choice_id if choice else None,
        "language": body.language,
        "answered_at": timeutil.utcnow(),
    }
    answers = [a for a in doc.get("answers", []) if a["question_id"] != body.question_id] + [entry]
    order = {qq["id"]: i for i, qq in enumerate(catalog.questions())}
    answers.sort(key=lambda a: order.get(a["question_id"], 99))
    now = timeutil.utcnow()
    await db["intake_sessions"].update_one({"_id": session_id}, {"$set": {"answers": answers, "updated_at": now}})
    return session_view({**doc, "answers": answers, "updated_at": now})


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def constraints_from(answers: list[dict[str, Any]]) -> Constraints:
    """Deterministic: each tapped choice carries the value it stands for."""
    values: dict[str, Any] = {}
    for a in answers:
        q = catalog.question(a["question_id"])
        if q is None or q["kind"] != "choice":
            continue
        choice = next((c for c in q["choices"] if c["id"] == a.get("choice_id")), None)
        if choice:
            values.update(choice["effect"])
    return Constraints(**values)


def _clean_phrase(value: str, low: int, high: int) -> str | None:
    text = scrub_text(value, limit=high).strip(" .,;:-")
    return text if low <= len(text) <= high and "[removed]" not in text else None


def normalise_extraction(raw: LLMExtraction) -> tuple[list[str], list[str], list[str], str | None]:
    """Vocabulary ids stay as skills; anything else becomes free text. Nothing unchecked is stored."""
    skills: list[str] = []
    other: list[str] = []
    for item in raw.skills:
        key = item.strip().lower().replace(" ", "_")
        if key in catalog.skill_ids():
            if key not in skills:
                skills.append(key)
        else:
            phrase = _clean_phrase(item, 2, 40)
            if phrase and phrase not in other:
                other.append(phrase)
    for item in raw.other_skills:
        phrase = _clean_phrase(item, 2, 40)
        if phrase and phrase.lower() not in [o.lower() for o in other]:
            other.append(phrase)
    interests = []
    for item in raw.interests:
        phrase = _clean_phrase(item, 2, 60)
        if phrase and phrase.lower() not in [i.lower() for i in interests]:
            interests.append(phrase)
    goal = _clean_phrase(raw.goal, 3, 160) if raw.goal else None
    return skills[:8], other[:5], interests[:6], goal


def _evidence_text(answers: list[dict[str, Any]]) -> str:
    """What the learner actually said in words: the open answers only, in their language and in English.
    Tapped choices and the picture tiles are not evidence of a skill."""
    parts = []
    for a in answers:
        q = catalog.question(a["question_id"])
        if q and q["kind"] == "open":
            parts.append(evidence.normalise(f"{a['transcript_native']} {a['transcript_en']}"))
    return evidence.SEGMENT.join(parts)


def supported_skills(skills: list[str], answers: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Splits proposed skill ids into (kept, dropped). A skill is kept only if the learner's words back it."""
    text = _evidence_text(answers)
    by_id = {s["id"]: s for s in catalog.skills()}
    kept = [s for s in skills if s in by_id and evidence.keyword_hits(by_id[s], text) > 0]
    return kept, [s for s in skills if s not in kept]


def keyword_extraction(answers: list[dict[str, Any]]) -> LLMExtraction:
    """Rule-based fallback: count vocabulary keywords in the learner's words, in any language."""
    text = _evidence_text(answers)
    scored: list[tuple[int, str]] = []
    for skill in catalog.skills():
        hits = evidence.keyword_hits(skill, text)
        if hits:
            scored.append((hits, skill["id"]))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return LLMExtraction(skills=[sid for _, sid in scored[:8]])


def extraction_schema() -> dict[str, Any]:
    """JSON schema for providers that can enforce one (Ollama). Skills may only be vocabulary ids,
    which stops a small model from echoing names or inventing ids."""
    schema = LLMExtraction.model_json_schema()
    schema["properties"]["skills"] = {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": sorted(catalog.skill_ids())}}
    # a 3B local model invents free-text skills, so the schema it must follow allows none; the vocabulary ids carry the signal
    schema["properties"]["other_skills"] = {"type": "array", "maxItems": 0}
    schema["properties"]["interests"] = {"type": "array", "maxItems": 4, "items": {"type": "string"}}
    return schema


def _extraction_prompt(doc: dict[str, Any], age_band: str | None) -> str:
    vocab = "\n".join(f"- {s['id']}: {s['name']['en']}" for s in catalog.skills())
    lines = []
    for a in doc.get("answers", []):
        q = catalog.question(a["question_id"])
        if q and q["kind"] == "open":
            lines.append(f"Q: {q['text']['en']}\nA: {a['transcript_en']}")
    return (
        f"Learner age band: {age_band or 'unknown'}\n"
        "\n"
        "Allowed skill ids:\n"
        f"{vocab}\n\n"
        "Answers:\n" + "\n\n".join(lines) + "\n\n"
        "Return JSON with these keys only:\n"
        '- "skills": ids from the allowed list, only for things the learner SAYS they do, have done or are learning. '
        "At most 3. If nothing clearly matches, use an empty list.\n"
        '- "other_skills": short English phrases for real skills the learner mentions that are not in the list. At most 3.\n'
        '- "interests": short English phrases for what the learner enjoys. At most 4.\n'
        '- "goal": one short English sentence about the work they want, or null.\n'
        "Never add a skill the learner did not mention.\n"
    )


async def _translate_pending(
    db: AsyncIOMotorDatabase, llm: LLMService, session_id: str, answers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Translates every answer still marked pending, all at once, and saves the result."""
    todo = [a for a in answers if a.get("translation") == "pending"]
    if not todo:
        return answers
    done = await asyncio.gather(*(_to_english(llm, a["transcript_native"], a.get("language", "en")) for a in todo))
    by_question = {a["question_id"]: pair for a, pair in zip(todo, done, strict=True)}
    updated = [
        {**a, "transcript_en": by_question[a["question_id"]][0], "translation": by_question[a["question_id"]][1]}
        if a["question_id"] in by_question
        else a
        for a in answers
    ]
    await db["intake_sessions"].update_one({"_id": session_id}, {"$set": {"answers": updated}})
    return updated


async def complete(
    db: AsyncIOMotorDatabase, llm: LLMService, user: dict[str, Any], session_id: str
) -> dict[str, Any]:
    doc = await _own_session(db, user, session_id)
    if doc["status"] not in ("in_progress", "review"):
        raise ApiError(409, "session_closed", "This intake is already finished.", "Start a new one.")
    answers = doc.get("answers", [])
    if len(answers) < MIN_ANSWERS:
        raise ApiError(409, "not_enough_answers", "A few more answers are needed.", "Answer the remaining questions.")

    answers = await _translate_pending(db, llm, session_id, answers)
    doc = {**doc, "answers": answers}

    profile = await db["student_profiles"].find_one({"user_id": user["_id"]}, {"age_band": 1})
    req = LLMRequest(
        task=Task.EXTRACTION,
        system=EXTRACT_SYSTEM,
        prompt=_extraction_prompt(doc, profile.get("age_band") if profile else None),
        schema=extraction_schema(),
        temperature=0.0,
        prompt_version=EXTRACT_VERSION,
    )
    result = await llm.generate(req, LLMExtraction, fallback=lambda: keyword_extraction(answers))
    skills, other, interests, goal = normalise_extraction(result.value)
    skills, dropped = supported_skills(skills, answers)
    if dropped:
        log.info("dropped skills with no support in the learner's words", extra={"count": len(dropped), "source": result.source})
    try:
        extracted = Extracted(skills=skills, other_skills=other, interests=interests, goal=goal, constraints=constraints_from(answers))
    except ValidationError as exc:  # cannot happen after normalise, but never store unchecked data
        log.error("extraction failed validation", extra={"error": type(exc).__name__})
        raise ApiError(502, "extraction_failed", "We could not read your answers.", "Please try again.") from exc

    now = timeutil.utcnow()
    stored = extracted.model_dump()
    await db["intake_sessions"].update_one(
        {"_id": session_id},
        {"$set": {"extracted": stored, "extraction_source": result.source, "extraction_model": result.model, "status": "review", "updated_at": now}},
    )
    return session_view({**doc, "extracted": stored, "extraction_source": result.source, "status": "review", "updated_at": now})


async def accept(db: AsyncIOMotorDatabase, user: dict[str, Any], session_id: str, body: AcceptIn) -> dict[str, Any]:
    doc = await _own_session(db, user, session_id)
    if doc["status"] != "review" or not doc.get("extracted"):
        raise ApiError(409, "nothing_to_accept", "There is no profile to confirm yet.", "Finish the questions first.")
    raw = LLMExtraction(skills=body.skills, other_skills=body.other_skills, interests=body.interests, goal=body.goal)
    skills, other, interests, goal = normalise_extraction(raw)
    previous = doc["extracted"]
    # Free text can only be kept or removed, never invented here. A skill from the controlled list may also be
    # ADDED: the learner is telling us themselves what they can do, which is their claim to make, not a guess.
    # `learner_added` keeps that apart from what was read from their words, for audit and for the evaluation.
    learner_added = [s for s in skills if s not in previous["skills"]]
    extracted = Extracted(
        skills=skills,
        learner_added=learner_added,
        other_skills=[o for o in other if o in previous["other_skills"]],
        interests=[i for i in interests if i in previous["interests"]],
        goal=goal if goal == previous.get("goal") else None,
        constraints=Constraints(**previous["constraints"]),
    )
    now = timeutil.utcnow()
    stored = extracted.model_dump()
    await db["intake_sessions"].update_one(
        {"_id": session_id}, {"$set": {"extracted": stored, "status": "done", "completed_at": now, "updated_at": now}}
    )
    return session_view({**doc, "extracted": stored, "status": "done", "updated_at": now})
