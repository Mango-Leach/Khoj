"""Ranks careers for a learner. Plain scoring code: the model never decides the order.

    score = 0.40 * skill match + 0.25 * local demand + 0.20 * first-income speed + 0.15 * feasibility

The weights are starting values chosen by the team (CLAUDE.md section 24, item 4) and are to be tuned on
labelled examples. Skill match uses only skills the learner HAS (read from their own words, or added by
them); the picture tiles they ticked add a small interest boost and can never create a strong match alone.
Local demand is a seeded judgement used for ordering only (data/demand_seed.json), never shown as a fact.
A learner sees their 3 best fits, then up to 3 more that are somewhat related ("also worth a look"). A career with no
real link to what they said (no matched or related skill, and not next to a strong match) is not shown at all, and a
ticked picture tile alone never makes a career worth showing. With too little to go on, they get 3 starting points,
labelled as such. Age never hides a path: a learner under 18 sees it, with a safety note on hazardous ones.
Eligibility for jobs and schemes is decided later, by the rules engine, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services import catalog

WEIGHTS = {"skill": 0.40, "demand": 0.25, "first_income": 0.20, "feasibility": 0.15}
BEST_COUNT = 3  # the best fits, shown first
ALSO_COUNT = 3  # somewhat related careers, shown after them
MIN_PATHS = BEST_COUNT
MAX_PATHS = BEST_COUNT + ALSO_COUNT
MIN_RELATED_SKILL = 0.1  # a "related" career needs at least this much real link to be worth a look

CORE_SHARE = 0.6  # matching 60% of a career's skill weight counts as a full match
RELATED_STEP = 0.12  # each related skill adds this much, up to RELATED_CAP
RELATED_CAP = 0.25
TILE_BOOST = 0.2  # a ticked picture tile in the career's family
GRAPH_FACTOR = 0.4  # a neighbour of a strong match gets this share of the link weight
STRONG_MATCH = 0.5
DEMAND = {"high": 1.0, "medium": 0.6, "low": 0.3}


@dataclass
class Profile:
    skills: set[str]
    tiles: set[str] = field(default_factory=set)  # career families the learner ticked: interest, not evidence
    budget: str = "unknown"  # none | low | medium | unknown
    can_move_away: str = "unknown"  # yes | no | unknown
    hours_per_week: int | None = None
    earned_before: str = "unknown"  # earned | helped | no | unknown
    priority: str = "unknown"  # earn_soon | earn_more | near_home | govt_job | own_business | unknown
    age: int | None = None
    district: str | None = None


@dataclass
class Ranked:
    career_id: str
    score: float
    factors: dict[str, float]
    matched: list[str]  # skills the learner has that this career needs
    related: list[str]  # skills the learner has that are close to what it needs
    via: str | None  # a strongly matching career this one was reached from
    tile: bool  # the learner ticked this career's family
    starter: bool  # included to reach the minimum, not because of a match
    tier: str  # best | also | starter
    fits: bool  # time, money and travel all suit the learner
    priority_fit: bool
    under18_theory_only: bool


# ---------------------------------------------------------------------------
# The four factors
# ---------------------------------------------------------------------------


def skill_factor(career: dict[str, Any], profile: Profile) -> tuple[float, list[str], list[str]]:
    required = career["required_skills"]
    total = sum(r["weight"] for r in required)
    matched = [r["skill"] for r in required if r["skill"] in profile.skills]
    matched_weight = sum(r["weight"] for r in required if r["skill"] in profile.skills)
    core = min(1.0, matched_weight / (CORE_SHARE * total)) if total else 0.0
    related = [s for s in career.get("related_skills", []) if s in profile.skills]
    partial = min(RELATED_CAP, RELATED_STEP * len(related))
    return min(1.0, core + partial), matched, related


def first_income_factor(career: dict[str, Any], profile: Profile, matched: bool) -> float:
    days = career["traits"]["first_income_days"]
    base = 1.0 if days <= 30 else 0.75 if days <= 60 else 0.5 if days <= 90 else 0.25
    if profile.earned_before == "earned" and matched:  # they have already earned from this kind of work
        base = min(1.0, base + 0.15)
    return base


def _budget_fit(cost: str, budget: str) -> float:
    if budget == "unknown":
        return 0.7
    table = {"none": {"none": 1.0, "low": 0.5, "medium": 0.1}, "low": {"none": 1.0, "low": 1.0, "medium": 0.4}, "medium": {"none": 1.0, "low": 1.0, "medium": 1.0}}
    return table[budget][cost]


def _hours_fit(min_hours: int, hours: int | None) -> float:
    if hours is None:
        return 0.7
    return 1.0 if hours >= min_hours else max(0.5, hours / min_hours)


def _travel_fit(needs_travel: bool, can_move: str) -> float:
    if not needs_travel:
        return 1.0
    return {"yes": 1.0, "no": 0.2, "unknown": 0.7}[can_move]


def _priority_fit(career: dict[str, Any], priority: str) -> float:
    t = career["traits"]
    if priority == "earn_soon":
        return 1.0 if t["first_income_days"] <= 60 else 0.5
    if priority == "earn_more":
        return {"high": 1.0, "medium": 0.7, "low": 0.4}[t["growth"]]
    if priority == "near_home":
        return 1.0 if t["works_near_home"] and not t["needs_travel"] else 0.4
    if priority == "govt_job":
        return 1.0 if career["family"] == "public" else 0.3
    if priority == "own_business":
        return 1.0 if t["self_employment"] else 0.5
    return 0.7


def feasibility_factor(career: dict[str, Any], profile: Profile) -> tuple[float, bool, bool]:
    t = career["traits"]
    parts = [_budget_fit(t["startup_cost"], profile.budget), _hours_fit(t["min_hours_per_week"], profile.hours_per_week), _travel_fit(t["needs_travel"], profile.can_move_away)]
    priority = _priority_fit(career, profile.priority)
    value = (sum(parts) + priority) / 4
    return value, min(parts) >= 0.7, profile.priority != "unknown" and priority >= 1.0


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank(profile: Profile) -> list[Ranked]:
    all_careers = catalog.careers()
    by_id = {c["career_id"]: c for c in all_careers}

    # 1. skill match, plus a small interest boost from ticked tiles
    skill: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    related: dict[str, list[str]] = {}
    tile: dict[str, bool] = {}
    for c in all_careers:
        cid = c["career_id"]
        s, m, r = skill_factor(c, profile)
        tile[cid] = c["family"] in profile.tiles
        skill[cid] = min(1.0, s + (TILE_BOOST if tile[cid] else 0.0))
        matched[cid], related[cid] = m, r

    # 2. widen through links: a close neighbour of a strong match gets a share of it
    via: dict[str, str] = {}
    strong = {cid: s for cid, s in skill.items() if s >= STRONG_MATCH and matched[cid]}
    for edge in catalog.career_edges():
        for a, b in ((edge["from"], edge["to"]), (edge["to"], edge["from"])):
            if a in strong:
                boosted = GRAPH_FACTOR * edge["weight"] * strong[a]
                if boosted > skill[b]:
                    skill[b], via[b] = boosted, a

    # 3. the other three factors, then the weighted total
    ranked: list[Ranked] = []
    for c in all_careers:
        cid = c["career_id"]
        demand = DEMAND[catalog.demand_level(cid, profile.district)]
        income = first_income_factor(c, profile, bool(matched[cid]))
        feasible, fits, priority_fit = feasibility_factor(c, profile)
        factors = {"skill": skill[cid], "demand": demand, "first_income": income, "feasibility": feasible}
        score = sum(WEIGHTS[k] * v for k, v in factors.items())
        ranked.append(
            Ranked(
                career_id=cid,
                score=round(score, 4),
                factors={k: round(v, 3) for k, v in factors.items()},
                matched=matched[cid],
                related=related[cid],
                via=via.get(cid) if not matched[cid] else None,
                tile=tile[cid],
                starter=False,
                tier="best",
                fits=fits,
                priority_fit=priority_fit,
                under18_theory_only=bool(profile.age is not None and profile.age < 18 and c["safety"]["under18_theory_only"]),
            )
        )

    # A path that builds on a skill the learner actually has always comes before one reached only through an
    # interest tile, a related skill or a link; within each group the weighted score decides.
    ranked.sort(key=lambda r: (0 if r.matched else 1, -r.score, r.career_id))
    # Only careers with a real link to what the learner said are worth showing. A ticked tile alone is not a link.
    linked = [r for r in ranked if r.matched or r.related or r.via]
    chosen = linked[:BEST_COUNT]
    also = [r for r in linked[BEST_COUNT:] if r.factors["skill"] >= MIN_RELATED_SKILL][:ALSO_COUNT]
    for r in also:
        r.tier = "also"
    if not linked:
        # Nothing linked at all (or "not sure"): offer 3 starting points. Families the learner ticked come first,
        # then the easiest places to start. They are labelled as starting points, not as matches. A learner with one or
        # two real matches sees just those: a filler career beside a real match would be noise.
        rest = [r for r in ranked if r not in chosen]
        rest.sort(key=lambda r: (0 if r.tile else 1, -(r.score if r.tile else r.factors["demand"] + r.factors["first_income"] + r.factors["feasibility"]), r.career_id))
        for r in rest[:BEST_COUNT]:
            r.starter, r.tier = True, "starter"
            chosen.append(r)
    chosen = chosen + also
    assert all(r.career_id in by_id for r in chosen)
    return chosen
