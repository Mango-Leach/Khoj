"""Career data, ranking, reasons, assessments and choosing a path. No network."""
from __future__ import annotations

import json
import re

import pytest

from app import deps, timeutil
from app.services import assessments as svc
from app.services import catalog, reasons
from app.services.career_engine import ALSO_COUNT, BEST_COUNT, MAX_PATHS, MIN_PATHS, Profile, rank
from tests.conftest import OTHER_PHONE, STUDENT, bearer, sign_in

API = "/api/v1"
FULL = {"tailoring_enterprise", "dairy_poultry", "electrician_wiring", "pump_motor_repair", "mobile_repair", "shop_accounting_gst", "digital_marketing_shops"}
HIGH_RISK = {"electrician_wiring", "pump_motor_repair", "solar_installer"}


@pytest.fixture(autouse=True)
def _fresh_llm_singleton():
    deps._llm_service = None
    yield
    deps._llm_service = None


# --- data integrity -----------------------------------------------------------


def test_catalogue_has_15_careers_7_in_full_depth_across_8_families():
    careers = catalog.careers()
    assert len(careers) == 15
    assert {c["career_id"] for c in careers if c["depth"] == "full"} == FULL
    assert len({c["family"] for c in careers}) == 8
    assert {c["family"] for c in careers} == {x["id"] for x in catalog.categories()}


def test_every_career_is_complete_and_references_real_skills():
    skill_ids = {s["id"] for s in catalog.skills()}
    for c in catalog.careers():
        cid = c["career_id"]
        for key in ("name", "summary", "first_income_step"):
            assert set(c[key]) == {"en", "hi", "mr"} and all(c[key].values()), (cid, key)
        assert len(c["ladder"]) == 5, cid
        assert c["sources"], cid
        for s in c["sources"]:
            assert s["url"].startswith("https://") and s["verified_on"] is None, cid  # never verified by a machine
        assert {r["skill"] for r in c["required_skills"]} <= skill_ids, cid
        assert set(c.get("related_skills", [])) <= skill_ids, cid
        assert c["safety"]["under18_theory_only"] == (cid in HIGH_RISK), cid


def test_career_data_never_states_a_money_figure():
    text = (catalog.DATA_DIR / "careers.json").read_text(encoding="utf-8")
    text = re.sub(r"https?://\S+", "", text)  # links contain %20-style escapes, which are not figures
    assert "₹" not in text
    assert not re.search(r"\b(rs\.?|inr|rupees?|lakh|crore)\s*\d|\d\s*(rs\b|rupees?|lakh|crore)", text, re.IGNORECASE)
    assert not re.search(r"\d+\s*%", text)


def test_edges_point_at_real_careers():
    ids = set(catalog.career_ids())
    for e in catalog.career_edges():
        assert e["from"] in ids and e["to"] in ids and 0 < e["weight"] <= 1


# --- ranking ------------------------------------------------------------------


def test_a_learner_who_sews_gets_tailoring_first():
    out = rank(Profile(skills={"sewing", "sewing_machine_care"}, age=16, district="pune"))
    assert out[0].career_id == "tailoring_enterprise"
    assert 1 <= len(out) <= MAX_PATHS
    assert "embroidery_zari" in [r.career_id for r in out]  # a close neighbour is widened in


def test_at_most_three_best_and_three_more_and_best_come_first():
    for p in (Profile(skills={"sewing", "bookkeeping", "house_wiring", "photography"}), Profile(skills={"house_wiring"}), Profile(skills={"sewing"})):
        out = rank(p)
        tiers = [r.tier for r in out]
        assert tiers.count("best") <= BEST_COUNT and tiers.count("also") <= ALSO_COUNT and len(out) <= MAX_PATHS
        assert tiers == sorted(tiers, key=["best", "also", "starter"].index), "best fits are listed before the rest"


def test_a_career_with_no_real_link_is_never_shown():
    """No matched skill, no related skill, and not next to a strong match: not worth a learner's time."""
    p = Profile(skills={"sewing"}, tiles={"agriculture", "trades"})
    shown = {r.career_id for r in rank(p)}
    assert not shown & {"dairy_poultry", "mushroom_beekeeping", "mobile_repair", "electrician_wiring", "solar_installer"}
    assert all(r.matched or r.related or r.via for r in rank(p))


def test_a_ticked_tile_alone_is_not_a_reason_to_show_a_career():
    out = rank(Profile(skills={"photography"}, tiles={"trades", "agriculture"}))
    assert all(r.matched or r.related or r.via for r in out)


def test_one_or_two_real_matches_are_shown_without_filler():
    out = rank(Profile(skills={"photography"}, tiles={"creative"}))
    assert 1 <= len(out) < BEST_COUNT + 1 and not any(r.starter for r in out)


def test_the_also_group_needs_a_real_link_of_some_size():
    out = rank(Profile(skills={"house_wiring"}, age=16))
    also = [r for r in out if r.tier == "also"]
    assert also and all((r.matched or r.related or r.via) and r.factors["skill"] >= 0.1 for r in also)


def test_not_sure_gives_three_labelled_starting_points():
    out = rank(Profile(skills=set()))
    assert len(out) == MIN_PATHS == BEST_COUNT and all(r.starter and r.tier == "starter" for r in out)


def test_ticked_tiles_with_no_skill_give_three_starting_points_from_those_families_first():
    out = rank(Profile(skills=set(), tiles={"textile"}))
    assert len(out) == 3 and all(r.starter and not r.matched for r in out)
    assert out[0].tile and out[0].career_id in {"tailoring_enterprise", "embroidery_zari"}


def test_matched_paths_always_come_before_unmatched_ones():
    out = rank(Profile(skills={"sewing"}, tiles={"agriculture"}))
    seen_unmatched = False
    for r in out:
        if not r.matched:
            seen_unmatched = True
        assert not (seen_unmatched and r.matched)


def test_age_never_hides_a_path_but_flags_the_hazardous_ones():
    skills = {"house_wiring"}
    minor = rank(Profile(skills=skills, age=15))
    adult = rank(Profile(skills=skills, age=19))
    assert [r.career_id for r in minor] == [r.career_id for r in adult]
    flagged = {r.career_id for r in minor if r.under18_theory_only}
    assert flagged and flagged <= HIGH_RISK
    assert not any(r.under18_theory_only for r in adult)


def test_ranking_is_deterministic():
    p = Profile(skills={"sewing", "bookkeeping"}, budget="low", priority="near_home", age=17, district="pune")
    assert [(r.career_id, r.score) for r in rank(p)] == [(r.career_id, r.score) for r in rank(p)]


def test_local_demand_nudges_order_but_not_past_a_direct_match():
    a = rank(Profile(skills={"sewing"}, district="kolhapur"))
    b = rank(Profile(skills={"sewing"}, district="mumbai_city"))
    assert a[0].career_id == b[0].career_id == "tailoring_enterprise"


# --- reasons ------------------------------------------------------------------


def test_template_reasons_exist_in_all_languages_and_pass_the_guard():
    for p in (Profile(skills={"sewing"}, priority="earn_soon"), Profile(skills=set(), tiles={"textile"}), Profile(skills=set())):
        for r in rank(p):
            out = reasons.build_reason(r, p.priority)
            assert set(out) == {"en", "hi", "mr"} and all(out.values())
            assert reasons.acceptable_reason(out["en"]), out["en"]


@pytest.mark.parametrize(
    "text",
    ["Earn 15,000 a month.", "It pays a good salary soon.", "There is huge demand for this work here.", "Short", "x" * 300, "It guarantees a job for you.", "Line one\nline two is here", 7, None],
)
def test_the_guard_rejects_claims_about_money_demand_and_numbers(text):
    assert not reasons.acceptable_reason(text)


def test_the_guard_accepts_a_plain_sentence():
    assert reasons.acceptable_reason("You already stitch clothes, so this builds on a skill you have.")


# --- API ----------------------------------------------------------------------


async def student(client, clock, phone="9876543210", profile=STUDENT):
    tokens = await sign_in(client, clock, phone)
    r = await client.post(f"{API}/students/profile", json=profile, headers=bearer(tokens))
    assert r.status_code == 201, r.text
    me = (await client.get(f"{API}/me", headers=bearer(tokens))).json()
    return tokens, me["id"]


async def finished_intake(db, user_id, skills=("sewing", "sewing_machine_care"), tiles=("textile",)):
    await db["intake_sessions"].insert_one(
        {
            "_id": f"intake-{user_id}",
            "user_id": user_id,
            "status": "done",
            "category_ids": list(tiles),
            "created_at": timeutil.utcnow(),
            "extracted": {
                "skills": list(skills),
                "learner_added": [],
                "other_skills": [],
                "interests": [],
                "goal": None,
                "constraints": {"budget": "low", "can_move_away": "no", "hours_per_week": 8, "earned_before": "earned", "priority": "earn_soon"},
            },
        }
    )


async def test_assessment_needs_a_finished_intake(client, clock):
    tokens, _ = await student(client, clock)
    r = await client.post(f"{API}/assessments", headers=bearer(tokens))
    assert r.status_code == 409 and r.json()["code"] == "intake_required"


async def test_assessment_returns_best_fits_first_with_reasons_and_no_money_or_demand(client, clock, db):
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid)
    r = await client.post(f"{API}/assessments", headers=bearer(tokens))
    assert r.status_code == 202, r.text
    body = r.json()
    assert 1 <= len(body["paths"]) <= MAX_PATHS
    assert {p["tier"] for p in body["paths"]} <= {"best", "also"}
    first = body["paths"][0]
    assert first["career_id"] == "tailoring_enterprise" and first["rank"] == 1
    assert set(first["reason"]) == {"en", "hi", "mr"} and set(first["first_income_step"]) == {"en", "hi", "mr"}
    dumped = json.dumps(body, ensure_ascii=False)
    assert "demand" not in {k for p in body["paths"] for k in p}  # demand never reaches the client
    assert "₹" not in dumped and "Demo data" not in dumped
    again = (await client.get(f"{API}/assessments/{body['id']}", headers=bearer(tokens))).json()
    assert len(again["paths"]) == len(body["paths"])
    assert (await client.get(f"{API}/assessments/latest", headers=bearer(tokens))).json()["id"] == body["id"]


async def test_a_minor_sees_all_paths_with_the_safety_flag_on_hazardous_ones(client, clock, db):
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid, skills=("house_wiring",), tiles=())
    body = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()
    by_id = {p["career_id"]: p for p in body["paths"]}
    assert "electrician_wiring" in by_id and by_id["electrician_wiring"]["under18_theory_only"] is True
    detail = (await client.get(f"{API}/careers/electrician_wiring", headers=bearer(tokens))).json()
    assert detail["safety"]["under18_theory_only"] and set(detail["safety"]["under18_note"]) == {"en", "hi", "mr"}


async def test_an_adult_has_no_safety_flag(client, clock, db):
    tokens, uid = await student(client, clock, profile={**STUDENT, "age": 20, "grade": 12})
    await finished_intake(db, uid, skills=("house_wiring",), tiles=())
    body = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()
    assert not any(p["under18_theory_only"] for p in body["paths"])


async def test_assessments_are_private_to_their_owner(client, clock, db):
    a, uid = await student(client, clock)
    await finished_intake(db, uid)
    aid = (await client.post(f"{API}/assessments", headers=bearer(a))).json()["id"]
    b, _ = await student(client, clock, phone=OTHER_PHONE, profile={**STUDENT, "name": "Other"})
    assert (await client.get(f"{API}/assessments/{aid}", headers=bearer(b))).status_code == 404
    assert (await client.get(f"{API}/assessments/latest", headers=bearer(b))).status_code == 404


async def test_career_endpoints_need_sign_in_and_hide_internals(client, clock):
    assert (await client.get(f"{API}/careers")).status_code == 401
    tokens, _ = await student(client, clock)
    lst = (await client.get(f"{API}/careers", headers=bearer(tokens))).json()["careers"]
    assert len(lst) == 15
    detail = (await client.get(f"{API}/careers/tailoring_enterprise", headers=bearer(tokens))).json()
    assert len(detail["ladder"]) == 5 and detail["sources"] and all(s["verified_on"] is None for s in detail["sources"])
    assert "first_income_days" not in detail["traits"] and "growth" not in detail["traits"]
    assert (await client.get(f"{API}/careers/nope", headers=bearer(tokens))).status_code == 404


async def test_select_creates_one_live_journey_and_replaces_the_earlier_choice(client, clock, db):
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid)
    body = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()
    ids = [p["career_id"] for p in body["paths"]]
    r1 = await client.post(f"{API}/careers/{ids[0]}/select", headers=bearer(tokens))
    assert r1.status_code == 201 and r1.json()["state"] == "path_selected"
    r2 = await client.post(f"{API}/careers/{ids[1]}/select", headers=bearer(tokens))
    assert r2.status_code == 201
    live = await db["journeys"].count_documents({"student_id": uid, "state": {"$ne": "abandoned"}})
    assert live == 1
    me = (await client.get(f"{API}/journeys/me", headers=bearer(tokens))).json()
    assert me["career"]["career_id"] == ids[1]


async def test_select_refuses_a_career_that_is_not_in_the_learners_paths(client, clock, db):
    tokens, uid = await student(client, clock)
    assert (await client.post(f"{API}/careers/tailoring_enterprise/select", headers=bearer(tokens))).status_code == 409  # no assessment
    await finished_intake(db, uid)
    body = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()
    outside = next(c for c in catalog.career_ids() if c not in {p["career_id"] for p in body["paths"]})
    r = await client.post(f"{API}/careers/{outside}/select", headers=bearer(tokens))
    assert r.status_code == 409 and r.json()["code"] == "not_in_paths"
    assert (await client.post(f"{API}/careers/nope/select", headers=bearer(tokens))).status_code == 404
    assert (await client.get(f"{API}/journeys/me", headers=bearer(tokens))).status_code == 404


async def test_only_students_can_use_assessments(client, clock):
    tokens = await sign_in(client, clock, "9876543210")  # signed in but no student role yet
    assert (await client.post(f"{API}/assessments", headers=bearer(tokens))).status_code == 403


# --- AI-written reasons -------------------------------------------------------


class _Scripted:
    def __init__(self, name, handler):
        self.name, self.handler = name, handler

    def model_for(self, req):
        return f"{self.name}-model"

    async def complete(self, req):
        return self.handler(req)


async def test_enrichment_replaces_the_english_reason_only_when_it_passes_the_guard(client, clock, db, settings):
    from app.services.cache import MemoryCache
    from app.services.llm import LLMService, Task

    good = "You already stitch clothes, so this builds straight on a skill you have."

    def handler(req):
        if req.task is Task.TRANSLATION:
            n = req.prompt.count("\n")
            return json.dumps({"hi": [f"हि{i}" for i in range(n)], "mr": [f"मर{i}" for i in range(n)]})
        return json.dumps({"reason": good if "Tailoring" in req.prompt else "Earn 20000 every month."})

    s = settings.model_copy(update={"llm_mode": "live", "llm_route_reasoning": "ollama", "llm_route_translation": "gemini"})
    llm = LLMService(s, {"ollama": _Scripted("ollama", handler), "gemini": _Scripted("gemini", handler)}, MemoryCache())
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid)
    aid = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()["id"]
    await svc.enrich(db, llm, aid, uid)
    doc = await db["assessments"].find_one({"_id": aid})
    assert doc["enrichment"] == "done"
    top = doc["paths"][0]
    assert top["reason"]["en"] == good and top["reason_source"]["en"] == "ai"
    for p in doc["paths"][1:3]:  # rejected sentences leave the template in place
        assert p["reason_source"]["en"] == "template" and "20000" not in p["reason"]["en"]


async def test_enrichment_failure_leaves_template_reasons(client, clock, db, settings):
    from app.services.cache import MemoryCache
    from app.services.llm import LLMService

    def boom(req):
        raise RuntimeError("down")

    s = settings.model_copy(update={"llm_mode": "live"})
    llm = LLMService(s, {"ollama": _Scripted("ollama", boom), "gemini": _Scripted("gemini", boom)}, MemoryCache())
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid)
    aid = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()["id"]
    before = await db["assessments"].find_one({"_id": aid})
    await svc.enrich(db, llm, aid, uid)
    after = await db["assessments"].find_one({"_id": aid})
    assert [p["reason"] for p in after["paths"]] == [p["reason"] for p in before["paths"]]


async def test_starting_points_keep_their_honest_template_and_the_model_is_not_asked(client, clock, db, settings):
    from app.services.cache import MemoryCache
    from app.services.llm import LLMService

    calls = []

    def handler(req):
        calls.append(req.task)
        return json.dumps({"reason": "You already stitch clothes, so this builds straight on a skill you have."})

    s = settings.model_copy(update={"llm_mode": "live"})
    llm = LLMService(s, {"ollama": _Scripted("ollama", handler), "gemini": _Scripted("gemini", handler)}, MemoryCache())
    tokens, uid = await student(client, clock)
    await finished_intake(db, uid, skills=(), tiles=())
    body = (await client.post(f"{API}/assessments", headers=bearer(tokens))).json()
    assert len(body["paths"]) == 3 and all(p["tier"] == "starter" and p["starter"] for p in body["paths"])
    await svc.enrich(db, llm, body["id"], uid)
    assert calls == []
    doc = await db["assessments"].find_one({"_id": body["id"]})
    assert all(p["reason_source"]["en"] == "template" for p in doc["paths"])


# --- translated ladders -------------------------------------------------------


def test_machine_translated_ladders_cover_every_career_with_five_rungs():
    translated = catalog.careers_i18n()
    assert set(translated) == set(catalog.career_ids())
    for cid, langs in translated.items():
        for lang in ("hi", "mr"):
            rungs = langs[lang]["ladder"]
            assert len(rungs) == 5 and all(r["title"].strip() and r["detail"].strip() for r in rungs), (cid, lang)


def test_career_detail_carries_translations_and_says_they_are_machine_made():
    detail = svc.career_detail(catalog.career("tailoring_enterprise"))
    assert set(detail["machine_translated"]) == {"hi", "mr"}
    assert all({"en", "hi", "mr"} <= set(r["title"]) for r in detail["ladder"])


# An assessment saved before the "3 best fits, then up to 3 also worth a look" rule holds up to 10 paths and no tier.
LEGACY = [
    # career, matched, related, via, skill factor
    ("photography_video", True, True, None, 1.0),
    ("childcare_tuition", True, False, None, 0.914),
    ("digital_marketing_shops", True, True, None, 0.528),
    ("embroidery_zari", True, False, None, 0.333),
    ("govt_exam_prep", True, False, None, 0.278),
    ("tailoring_enterprise", False, True, None, 0.12),
    ("mobile_repair", False, False, None, 0.2),  # no real link: never shown
    ("shop_accounting_gst", False, False, "digital_marketing_shops", 0.063),  # linked, but too weak to be worth a look
    ("electrician_wiring", False, False, None, 0.2),
    ("solar_installer", False, False, None, 0.2),
]


async def test_an_old_assessment_is_cut_down_to_best_fits_and_a_few_more(client, clock, db):
    tokens, uid = await student(client, clock)
    await db["assessments"].insert_one(
        {
            "_id": "legacy",
            "user_id": uid,
            "intake_id": "x",
            "created_at": clock.now,
            "based_on": {"skills": ["photography"]},
            "weights": {},
            "paths": [
                {"rank": i + 1, "career_id": c, "score": 0.5, "factors": {"skill": f, "demand": 0.5, "first_income": 0.5, "feasibility": 0.5}, "reason": {"en": "r", "hi": "r", "mr": "r"},
                 "matched": ["photography"] if m else [], "related": ["video_editing"] if r else [], "via": v, "starter": False, "under18_theory_only": False}
                for i, (c, m, r, v, f) in enumerate(LEGACY)
            ],
        }
    )
    body = (await client.get(f"{API}/assessments/legacy", headers=bearer(tokens))).json()
    shown = [(p["career_id"], p["tier"]) for p in body["paths"]]
    assert shown == [
        ("photography_video", "best"),
        ("childcare_tuition", "best"),
        ("digital_marketing_shops", "best"),
        ("embroidery_zari", "also"),
        ("govt_exam_prep", "also"),
        ("tailoring_enterprise", "also"),
    ]
    # a path that is no longer shown cannot be picked either, and one that is shown still can
    gone = await client.post(f"{API}/careers/mobile_repair/select", headers=bearer(tokens))
    assert gone.status_code == 409 and gone.json()["code"] == "not_in_paths"
    assert (await client.post(f"{API}/careers/digital_marketing_shops/select", headers=bearer(tokens))).status_code == 201
