"""The job knowledge pack (CLAUDE.md section 9), shown after a learner finishes a path.

It is built from data the team has already entered and cited, so it never says anything new on its own account:
- the papers the linked programmes ask for, plus a short list of papers many programmes ask for;
- how to apply to each linked programme, with its source;
- questions to practise for a first conversation with an employer or an office;
- courses to take next, linked out;
- a safety note for a high-risk trade.

The spec also lists local employers and wage notes, and rights at work. Those need sourced local data we do not have
yet, so they are left out rather than invented.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.errors import ApiError
from app.services import catalog, opportunities
from app.services.opportunities import career_fit, rule_of

# Papers many programmes ask for. Shown as "usually asked": each programme's own list decides.
USUAL_DOCS = ("aadhaar", "bank_account", "school_marksheet", "photo")
PITCH_QUESTIONS = ("intro", "work", "learned", "why")


async def build(db: AsyncIOMotorDatabase, user: dict[str, Any], career_id: str) -> dict[str, Any]:
    career = catalog.career(career_id)
    if career is None:
        raise ApiError(404, "career_not_found", "We could not find that career.", "")
    # only a learner who finished this path gets its pack
    try:
        await opportunities.latest_finished(db, user, career_id)
    except ApiError as err:
        raise ApiError(409, "pack_locked", "The job pack opens when you finish this path.", "Finish your steps with your mentor first.") from err

    # the ones made for this path come first, then the ones open to any path
    fits = [(o, career_fit(o, career)) for o in catalog.opportunities()]
    linked = [o for o, fit in sorted((x for x in fits if x[1] is not None), key=lambda x: (-x[1][0], x[0]["id"]))]
    programme_docs: list[str] = []
    steps = []
    for opp in linked:
        rule = rule_of(opp)
        for doc in rule.get("docs_required", []):
            if doc not in programme_docs:
                programme_docs.append(doc)
        steps.append(
            {
                "opportunity_id": opp["id"],
                "title": opp["title_i18n"],
                "how": opp["how_i18n"],
                "apply_url": opp["apply_url"],
                "source": {"title": rule["source_title"], "url": rule["source_url"], "verified_on": rule.get("verified_on")},
            }
        )
    courses = [
        {"id": r["id"], "title": r["title"], "provider": r["provider"], "url": r["url"], "rung": r.get("rung"), "verified_on": r.get("verified_on")}
        for r in catalog.resources_for(career_id)
    ]
    return {
        "career_id": career_id,
        "documents": {"asked": programme_docs, "usual": [d for d in USUAL_DOCS if d not in programme_docs]},
        "steps": steps,
        "pitch": list(PITCH_QUESTIONS),
        "courses": courses,
        "learn_links": career.get("learn_links", []),
        "safety": {"class": career["safety"]["class"], "in_person_check_needed": career["safety"]["class"] == "high"},
        "machine_translated": opportunities.MACHINE_TRANSLATED,
    }
