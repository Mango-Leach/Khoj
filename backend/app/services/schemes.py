"""Scholarships and schemes: checks a learner against the rule files (M4).

The decision is made by `rules_engine.evaluate`, in plain code. This layer only gathers facts and shapes the answer.
Facts come from two places: the learner's saved profile (age, class, state; read on the server, never trusted from the
client) and the few answers the learner types for this check. Those answers are NOT saved. Only the facts a scheme
needs are ever asked for, and income is asked only when a scheme being checked has an income limit.
"""
from __future__ import annotations

from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field

from app import timeutil
from app.config import Settings
from app.errors import ApiError
from app.services import catalog, rules_engine

# Facts that come from the saved profile. Everything else is asked.
PROFILE_FACTS = ("age", "grade", "state")

# The order questions are shown in. A fact not listed here is never asked.
ASK_ORDER = (
    "social_category",
    "annual_income_inr",
    "school_type",
    "in_professional_course",
    "qualification",
    "works_in_listed_trade",
    "govt_service_in_family",
    "took_similar_loan_5y",
)

# A paper that proves the answer to a question. Shown as "papers to prepare" next to a scheme that asks it.
FACT_DOCS = {
    "annual_income_inr": "income_certificate",
    "social_category": "category_certificate",
}

STATUS_ORDER = {rules_engine.ELIGIBLE: 0, rules_engine.CHECK: 1, rules_engine.NOT_ELIGIBLE: 2}

SocialCategory = Literal["sc", "st", "obc", "dnt", "ebc", "general"]
SchoolType = Literal["government", "government_aided", "local_body", "private", "central_residential"]
Qualification = Literal["none", "diploma", "vocational_certificate", "graduate"]


class SchemeFacts(BaseModel):
    """What the learner may tell us for a check. Every field is optional: not answering is allowed
    and simply makes a scheme say "Check with the office"."""

    model_config = ConfigDict(extra="forbid")

    annual_income_inr: int | None = Field(default=None, ge=0, le=100_000_000)
    social_category: SocialCategory | None = None
    school_type: SchoolType | None = None
    in_professional_course: bool | None = None
    qualification: Qualification | None = None
    works_in_listed_trade: bool | None = None
    govt_service_in_family: bool | None = None
    took_similar_loan_5y: bool | None = None


class SchemeCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: SchemeFacts = Field(default_factory=SchemeFacts)
    scheme_ids: list[str] | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _translations(scheme: dict[str, Any]) -> dict[str, Any]:
    """Machine translations by language: {"hi": {"name": ..., "summary": ..., "note": ..., "conditions": [...]}}."""
    return catalog.schemes_i18n().get(scheme["id"]) or {}


def _text(scheme: dict[str, Any], key: str) -> dict[str, str]:
    """English from the rule file, plus Hindi and Marathi where a machine translation exists."""
    out = dict(scheme.get(f"{key}_i18n") or {})
    for lang, block in _translations(scheme).items():
        if block.get(key):
            out[lang] = block[key]
    return out


def _label(scheme: dict[str, Any], index: int) -> dict[str, str]:
    out = dict(scheme["conditions"][index].get("label_i18n") or {})
    for lang, block in _translations(scheme).items():
        labels = block.get("conditions") or []
        if index < len(labels) and labels[index]:
            out[lang] = labels[index]
    return out


def machine_translated_langs(scheme: dict[str, Any]) -> list[str]:
    return sorted(_translations(scheme).keys())


def needs(scheme: dict[str, Any]) -> list[str]:
    """Facts this scheme needs from the learner that the profile does not hold. Placeholders are not asked."""
    wanted = {
        c["fact"]
        for c in scheme["conditions"]
        if c["fact"] not in PROFILE_FACTS and not rules_engine.is_placeholder(c.get("value")) and c["fact"] in ASK_ORDER
    }
    return [f for f in ASK_ORDER if f in wanted]


def _base(scheme: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": scheme["id"],
        "name": _text(scheme, "name"),
        "summary": _text(scheme, "summary"),
        "note": _text(scheme, "note"),
        "level": scheme["level"],
        "apply_url": scheme.get("apply_url"),
        "needs": needs(scheme),
        "machine_translated": machine_translated_langs(scheme),
        "source": {
            "title": scheme["source_title"],
            "url": scheme["source_url"],
            "entered_on": scheme["entered_on"],
            "verified_on": scheme.get("verified_on"),
            "awaiting_verification": not scheme.get("verified_on"),
        },
    }


def list_schemes() -> list[dict[str, Any]]:
    return [_base(s) for s in catalog.schemes()]


def _opens_at(scheme: dict[str, Any], failed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For an age or class limit the learner has not reached yet: "opens at age 18"."""
    out = []
    for cond in scheme["conditions"]:
        if cond["fact"] in ("age", "grade") and cond["op"] == ">=" and any(f["fact"] == cond["fact"] for f in failed):
            out.append({"fact": cond["fact"], "value": cond["value"]})
    return out


def result_view(scheme: dict[str, Any], facts: dict[str, Any], today, max_days: int) -> dict[str, Any]:
    r = rules_engine.evaluate(scheme, facts, today, max_days)

    def shape(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"fact": i["fact"], "label": _label(scheme, i["index"])} for i in items]

    docs = list(r["docs_to_prepare"])
    for item in r["passed"] + r["missing"]:
        doc = FACT_DOCS.get(item["fact"])
        if doc and doc not in docs:
            docs.append(doc)
    return {
        **_base(scheme),
        "status": r["status"],
        "passed": shape(r["passed"]),
        "failed": shape(r["failed"]),
        "missing": shape(r["missing"]),
        "unresolved": shape(r["unresolved"]),
        "opens_at": _opens_at(scheme, r["failed"]),
        "docs": docs,
        "stale": r["stale"],
        "expired": r["expired"],
    }


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


async def profile_facts(db: AsyncIOMotorDatabase, user: dict[str, Any]) -> dict[str, Any]:
    doc = await db["student_profiles"].find_one({"user_id": user["_id"]})
    if doc is None:
        raise ApiError(409, "profile_required", "Please fill in your profile first.", "We need your age and class to check schemes.")
    return {"age": doc["age"], "grade": doc["grade"], "state": str(doc["state"]).lower()}


async def check(db: AsyncIOMotorDatabase, user: dict[str, Any], body: SchemeCheckIn, settings: Settings) -> dict[str, Any]:
    facts = await profile_facts(db, user)
    given = body.facts.model_dump(exclude_none=True)
    facts.update(given)  # the learner's answers never replace what the profile says about age, class or state

    chosen = catalog.schemes()
    if body.scheme_ids is not None:
        unknown = [i for i in body.scheme_ids if catalog.scheme(i) is None]
        if unknown:
            raise ApiError(404, "scheme_not_found", "We could not find that scheme.", "")
        chosen = [s for s in chosen if s["id"] in body.scheme_ids]

    today = timeutil.utcnow().date()
    results = [result_view(s, facts, today, settings.verified_max_days) for s in chosen]
    results.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["id"]))

    # What is still worth asking: facts that a not-yet-decided scheme is waiting on.
    waiting = {m["fact"] for r in results if r["status"] == rules_engine.CHECK for m in r["missing"]}
    return {
        "results": results,
        "ask": [f for f in ASK_ORDER if f in waiting],
        "counts": {k: sum(1 for r in results if r["status"] == k) for k in STATUS_ORDER},
    }
