from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache
def districts() -> list[dict[str, Any]]:
    with open(DATA_DIR / "maharashtra_districts.json", encoding="utf-8") as f:
        return json.load(f)["districts"]


@lru_cache
def district_ids() -> frozenset[str]:
    return frozenset(d["id"] for d in districts())


def _load(name: str) -> dict[str, Any]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def categories() -> list[dict[str, Any]]:
    """The eight career families shown as picture tiles."""
    return _load("intake_categories.json")["categories"]


@lru_cache
def category_ids() -> frozenset[str]:
    return frozenset(c["id"] for c in categories())


@lru_cache
def skills() -> list[dict[str, Any]]:
    """The controlled skill vocabulary. Keywords are for the fallback matcher, not for display."""
    return _load("skills.json")["skills"]


@lru_cache
def skill_ids() -> frozenset[str]:
    return frozenset(s["id"] for s in skills())


@lru_cache
def questions() -> list[dict[str, Any]]:
    return _load("intake_questions.json")["questions"]


def question(question_id: str) -> dict[str, Any] | None:
    return next((q for q in questions() if q["id"] == question_id), None)



# ---------------------------------------------------------------------------
# Careers (M3)
# ---------------------------------------------------------------------------


@lru_cache
def careers() -> list[dict[str, Any]]:
    return _load("careers.json")["careers"]


@lru_cache
def career_ids() -> frozenset[str]:
    return frozenset(c["career_id"] for c in careers())


def career(career_id: str) -> dict[str, Any] | None:
    return next((c for c in careers() if c["career_id"] == career_id), None)


@lru_cache
def career_edges() -> list[dict[str, Any]]:
    return _load("career_edges.json")["edges"]


@lru_cache
def demand_seed() -> dict[str, Any]:
    return _load("demand_seed.json")


def demand_level(career_id: str, district: str | None) -> str:
    """Seeded local demand for ranking only: high, medium or low. Never shown to students."""
    seed = demand_seed()
    if district and career_id in seed["districts"].get(district, {}):
        return seed["districts"][district][career_id]
    return seed["default"].get(career_id, "medium")


@lru_cache
def resources() -> list[dict[str, Any]]:
    """Courses and learning material, linked out (M4b). Each is a title, a provider and a URL; nothing is copied."""
    return _load("resources.json")["resources"]


def resources_for(career_id: str) -> list[dict[str, Any]]:
    return [r for r in resources() if career_id in r["career_ids"]]


@lru_cache
def schemes() -> list[dict[str, Any]]:
    """Scheme rules, one JSON file each in data/schemes/ (M4). Sorted by id so the order is stable."""
    folder = DATA_DIR / "schemes"
    out = []
    for path in sorted(folder.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def scheme(scheme_id: str) -> dict[str, Any] | None:
    return next((s for s in schemes() if s["id"] == scheme_id), None)


@lru_cache
def opportunities() -> list[dict[str, Any]]:
    """Programmes and portals a finished learner can go to (M8), linked out. Sorted by id so the order is stable."""
    return sorted(_load("opportunities.json")["opportunities"], key=lambda o: o["id"])


def opportunity(opportunity_id: str) -> dict[str, Any] | None:
    return next((o for o in opportunities() if o["id"] == opportunity_id), None)


@lru_cache
def schemes_i18n() -> dict[str, Any]:
    """Machine-translated scheme text (Hindi, Marathi), made by scripts/translate_schemes.py. May be empty."""
    try:
        return _load("schemes_i18n.json").get("schemes", {})
    except FileNotFoundError:
        return {}


@lru_cache
def careers_i18n() -> dict[str, Any]:
    """Machine-translated ladder text (Hindi, Marathi), made by scripts/translate_careers.py. May be empty."""
    try:
        return _load("careers_i18n.json").get("careers", {})
    except FileNotFoundError:
        return {}


@lru_cache
def teacher_tests() -> dict[str, Any]:
    """The teacher practical test (M5): areas, sample work descriptions and the team's placeholder expert scores."""
    return _load("teacher_tests.json")


def test_area(area_id: str) -> dict[str, Any] | None:
    return next((a for a in teacher_tests()["areas"] if a["id"] == area_id), None)
