"""Mentor matching (CLAUDE.md section 10). Plain scoring code, no model.

    match = 0.35 S + 0.20 L + 0.15 A + 0.20 T + 0.10 P

Hard filters run first: tier 1 or above, at least one of the career's required skills verified, and a free place.
The weights are starting values for the team to tune.
"""
from __future__ import annotations

import math
from typing import Any

WEIGHTS = {"skill": 0.35, "language": 0.20, "capacity": 0.15, "trust": 0.20, "place": 0.10}
NEUTRAL_TRUST = 0.5  # a mentor with no history yet starts in the middle, not at the bottom
CANDIDATES = 3


def skill_similarity(required: list[dict[str, Any]], verified: set[str]) -> float:
    """Cosine between the career's weighted required skills and the mentor's verified skills (each counted once)."""
    weights = {r["skill"]: float(r["weight"]) for r in required}
    if not weights or not verified:
        return 0.0
    dot = sum(w for skill, w in weights.items() if skill in verified)
    norm = math.sqrt(sum(w * w for w in weights.values())) * math.sqrt(len(verified))
    return dot / norm if norm else 0.0


def language_fit(teacher_languages: list[str], student_language: str) -> float:
    """1 if the mentor speaks the learner's language, 0.5 if translation would have to help."""
    return 1.0 if student_language in teacher_languages else 0.5


def capacity_fit(free: int, limit: int) -> float:
    return max(0.0, min(1.0, free / limit)) if limit > 0 else 0.0


def trust_fit(trust: float | None) -> float:
    return NEUTRAL_TRUST if trust is None else max(0.0, min(1.0, float(trust)))


def place_fit(teacher_block: str, teacher_district: str, student_block: str, student_district: str) -> float:
    if teacher_district != student_district:
        return 0.0
    return 1.0 if teacher_block.strip().casefold() == student_block.strip().casefold() else 0.5


def passes_hard_filters(tier: int, verified_required: int, free: int) -> bool:
    return tier >= 1 and verified_required >= 1 and free > 0


def verified_skill_set(teacher: dict[str, Any]) -> set[str]:
    return {s["tag"] for s in teacher.get("skills", []) if s.get("verified")}


def score(career: dict[str, Any], teacher: dict[str, Any], student: dict[str, Any], student_language: str, free: int, limit: int) -> dict[str, Any] | None:
    """The match score and its parts, or None when the mentor fails a hard filter."""
    verified = verified_skill_set(teacher)
    required = career["required_skills"]
    required_ids = {r["skill"] for r in required}
    overlap = verified & required_ids
    if not passes_hard_filters(teacher.get("tier", 0), len(overlap), free):
        return None
    factors = {
        "skill": skill_similarity(required, verified),
        "language": language_fit(teacher["languages"], student_language),
        "capacity": capacity_fit(free, limit),
        "trust": trust_fit(teacher.get("trust")),
        "place": place_fit(teacher["block"], teacher["district"], student["block"], student["district"]),
    }
    total = sum(WEIGHTS[k] * v for k, v in factors.items())
    return {"score": round(total, 4), "factors": {k: round(v, 4) for k, v in factors.items()}, "skills": sorted(overlap)}


def top_candidates(scored: list[tuple[dict[str, Any], dict[str, Any]]], limit: int = CANDIDATES) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Best first. Ties break on the teacher id so the same inputs always give the same three."""
    return sorted(scored, key=lambda pair: (-pair[1]["score"], pair[0]["_id"]))[:limit]
