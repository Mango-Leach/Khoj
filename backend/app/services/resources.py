"""Learning resources: courses and material linked out from the career pages (and, later, the job knowledge pack).

Nothing is copied or hosted. Each record is a title, a provider and a URL a person found on the provider's own site.
`verified_on` is empty until a person opens the page and checks it, and the screen says so.
"""
from __future__ import annotations

from typing import Any

from app.errors import ApiError
from app.services import catalog


def view(res: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": res["id"],
        "title": res["title"],
        "provider": res["provider"],
        "kind": res["kind"],
        "url": res["url"],
        "level": res.get("level"),
        "duration_weeks": res.get("duration_weeks"),
        "languages": res.get("languages", []),
        "cost": res.get("cost"),
        "entry": res.get("entry"),
        "found_on": res["found_on"],
        "verified_on": res.get("verified_on"),
        "awaiting_verification": not res.get("verified_on"),
    }


def for_career(career_id: str) -> list[dict[str, Any]]:
    return [view(r) for r in catalog.resources_for(career_id)]


def listing(career_id: str | None) -> list[dict[str, Any]]:
    if career_id is None:
        return [view(r) for r in catalog.resources()]
    if catalog.career(career_id) is None:
        raise ApiError(404, "career_not_found", "We could not find that path.", "")
    return for_career(career_id)
