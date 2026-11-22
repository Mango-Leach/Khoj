"""M5: teacher skill check, tiers, mentor matching and the request flow."""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.config import Settings
from app.services import catalog, journeys, matching, teacher_assessment
from tests.conftest import OTP, bearer, sign_in

API = "/api/v1"
ADMIN_PHONE = "9111111111"
PHONES = [f"90000000{n:02d}" for n in range(10, 30)]

TEACHER = {"name": "Sunita", "roles": ["teacher"], "languages": ["mr", "hi"], "district": "pune", "block": "Haveli", "weekly_hours": 6}
STUDENT = {"name": "Priya", "age": 17, "grade": 11, "district": "pune", "block": "Haveli", "guardian_consent": True}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_mode=True,
        demo_phones="*",
        admin_phones=ADMIN_PHONE,
        jwt_secret="test-secret-0123456789-0123456789-xyz",
        otp_per_ip_per_10min=1000,
        otp_per_phone_per_10min=1000,
    )


def perfect_scores(area_id: str) -> dict[str, int]:
    return {i["id"]: i["expert_score"] for i in catalog.test_area(area_id)["items"]}


def required(career_id: str) -> list[dict]:
    return catalog.career(career_id)["required_skills"]


# ---------------------------------------------------------------------------
# Pure scoring
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    assert sum(matching.WEIGHTS.values()) == pytest.approx(1.0)


def test_skill_similarity_prefers_a_closer_skill_match():
    req = required("tailoring_enterprise")
    full = {"sewing", "sewing_machine_care", "garment_finishing"}
    partial = {"sewing"}
    assert matching.skill_similarity(req, full) > matching.skill_similarity(req, partial) > 0
    assert matching.skill_similarity(req, set()) == 0
    assert matching.skill_similarity(req, {"house_wiring"}) == 0


def test_skill_similarity_is_diluted_by_unrelated_skills():
    req = required("tailoring_enterprise")
    focused = {"sewing", "sewing_machine_care"}
    broad = focused | {"house_wiring", "mobile_repair", "bookkeeping"}
    assert matching.skill_similarity(req, focused) > matching.skill_similarity(req, broad)


def test_factor_functions():
    assert matching.language_fit(["mr", "hi"], "hi") == 1.0
    assert matching.language_fit(["mr"], "hi") == 0.5
    assert matching.capacity_fit(5, 5) == 1.0 and matching.capacity_fit(0, 5) == 0.0 and matching.capacity_fit(1, 0) == 0.0
    assert matching.trust_fit(None) == matching.NEUTRAL_TRUST
    assert matching.trust_fit(1.7) == 1.0 and matching.trust_fit(-1) == 0.0
    assert matching.place_fit("Haveli", "pune", "haveli ", "pune") == 1.0
    assert matching.place_fit("Mulshi", "pune", "Haveli", "pune") == 0.5
    assert matching.place_fit("Haveli", "pune", "Haveli", "nashik") == 0.0  # same block name in another district is not "same place"


def test_hard_filters():
    assert matching.passes_hard_filters(1, 1, 1)
    assert not matching.passes_hard_filters(0, 3, 5)  # unverified
    assert not matching.passes_hard_filters(1, 0, 5)  # no required skill verified
    assert not matching.passes_hard_filters(1, 2, 0)  # full


def _teacher(tid: str, *, tier=1, skills=("sewing",), langs=("mr",), block="Haveli", district="pune", trust=None) -> dict:
    return {
        "_id": tid, "tier": tier, "languages": list(langs), "block": block, "district": district, "trust": trust,
        "skills": [{"tag": s, "level": None, "verified": True} for s in skills],
    }


def test_score_returns_none_for_a_failed_hard_filter():
    career = catalog.career("tailoring_enterprise")
    student = {"block": "Haveli", "district": "pune"}
    assert matching.score(career, _teacher("a", tier=0), student, "mr", 5, 5) is None
    assert matching.score(career, _teacher("a", skills=("house_wiring",)), student, "mr", 5, 5) is None
    assert matching.score(career, _teacher("a"), student, "mr", 0, 5) is None
    assert matching.score(career, _teacher("a"), student, "mr", 5, 5) is not None


def test_a_skill_that_is_claimed_but_not_verified_does_not_count():
    career = catalog.career("tailoring_enterprise")
    t = _teacher("a")
    t["skills"][0]["verified"] = False
    assert matching.score(career, t, {"block": "x", "district": "pune"}, "mr", 5, 5) is None


def test_top_candidates_is_deterministic_and_capped():
    pairs = [({"_id": f"t{i}"}, {"score": 0.5}) for i in (3, 1, 2, 5, 4)]
    first = matching.top_candidates(pairs)
    assert [t["_id"] for t, _ in first] == ["t1", "t2", "t3"]
    assert matching.top_candidates(list(reversed(pairs))) == first
    better = pairs + [({"_id": "t9"}, {"score": 0.9})]
    assert matching.top_candidates(better)[0][0]["_id"] == "t9"


def test_journey_state_machine():
    assert journeys.can_move("path_selected", "mentor_pending")
    assert journeys.can_move("mentor_pending", "in_progress")
    assert journeys.can_move("mentor_pending", "path_selected")  # declined or lapsed
    assert not journeys.can_move("path_selected", "in_progress")  # a mentor must say yes first
    assert not journeys.can_move("in_progress", "mentor_pending")
    assert not journeys.can_move("abandoned", "in_progress") and not journeys.can_move("enrolled", "in_progress")
    assert set(journeys.sources_for("in_progress")) >= {"mentor_pending", "stalled"}


def test_pass_rule_four_of_five_within_one_point():
    area = catalog.test_area("tailoring")
    expert = {i["id"]: i["expert_score"] for i in area["items"]}
    assert teacher_assessment.score_attempt(area, expert) == 5
    off_by_one = {k: min(4, v + 1) if v < 4 else v - 1 for k, v in expert.items()}
    assert teacher_assessment.score_attempt(area, off_by_one) == 5
    two_wrong = dict(expert)
    for k in list(expert)[:2]:
        two_wrong[k] = 1 if expert[k] >= 3 else 4  # more than one point away from the expert
    assert teacher_assessment.score_attempt(area, two_wrong) == 3
    one_wrong = dict(expert)
    k = list(expert)[0]
    one_wrong[k] = 1 if expert[k] >= 3 else 4
    assert teacher_assessment.score_attempt(area, one_wrong) == 4  # 4 of 5 still passes


def test_tier_needs_both_layers():
    assert teacher_assessment.tier_for("verified", ["tailoring"]) == 1
    assert teacher_assessment.tier_for("verified", []) == 0
    assert teacher_assessment.tier_for("pending", ["tailoring"]) == 0
    assert teacher_assessment.tier_for("rejected", ["tailoring"]) == 0
    assert teacher_assessment.tier_for("none", ["tailoring"], current_tier=2) == 2  # outcomes-based tier is not lowered here


def test_every_test_area_is_well_formed():
    data = catalog.teacher_tests()
    for area in data["areas"]:
        assert len(area["items"]) == data["pass_rule"]["items"]
        assert all(1 <= i["expert_score"] <= 4 for i in area["items"])
        assert set(area["verifies"]) <= catalog.skill_ids()
        assert all(catalog.career(c) for c in area["career_ids"])
        # each area proves at least one skill its career needs, or matching could never use it
        for cid in area["career_ids"]:
            assert set(area["verifies"]) & {r["skill"] for r in required(cid)}


# ---------------------------------------------------------------------------
# Helpers for the API tests
# ---------------------------------------------------------------------------


async def make_teacher(client, clock, db, phone, *, tier=1, areas=("tailoring",), block="Haveli", district="pune", languages=("mr", "hi"), name="Sunita", trust=None):
    """A signed-in teacher. With tier 1 the evidence and tests are set directly in the database; the API path has its own tests."""
    tokens = await sign_in(client, clock, phone)
    r = await client.post(f"{API}/teachers/profile", headers=bearer(tokens), json={**TEACHER, "name": name, "block": block, "district": district, "languages": list(languages)})
    assert r.status_code == 201, r.text
    doc = await db["teacher_profiles"].find_one({"user_id": tokens["user"]["id"]})
    if tier:
        merged = {**doc, "passed_areas": list(areas), "evidence": {"status": "verified"}}
        update = {"passed_areas": list(areas), "evidence": {"status": "verified"}, "trust": trust, **teacher_assessment.recompute(merged)}
        await db["teacher_profiles"].update_one({"_id": doc["_id"]}, {"$set": update})
    return tokens, doc["_id"]


async def make_student(client, clock, db, phone, career_id="tailoring_enterprise", **profile):
    tokens = await sign_in(client, clock, phone)
    r = await client.post(f"{API}/students/profile", headers=bearer(tokens), json={**STUDENT, **profile})
    assert r.status_code == 201, r.text
    user_id = tokens["user"]["id"]
    await db["assessments"].insert_one(
        {"_id": uuid.uuid4().hex, "user_id": user_id, "created_at": clock.now, "based_on": {"skills": ["sewing"]}, "paths": [{"career_id": career_id}]}
    )
    r = await client.post(f"{API}/careers/{career_id}/select", headers=bearer(tokens))
    assert r.status_code == 201, r.text
    return tokens, r.json()["id"], user_id


async def candidates(client, tokens, journey_id):
    r = await client.get(f"{API}/journeys/{journey_id}/match-mentor", headers=bearer(tokens))
    assert r.status_code == 200, r.text
    return r.json()["candidates"]


# ---------------------------------------------------------------------------
# Skill check and tiers (API)
# ---------------------------------------------------------------------------


async def test_a_new_teacher_is_tier_zero_and_cannot_be_matched(client, clock, db):
    t_tokens, _ = await make_teacher(client, clock, db, PHONES[0], tier=0)
    me = (await client.get(f"{API}/teachers/me", headers=bearer(t_tokens))).json()
    assert me["tier"] == 0 and me["capacity"] == {"limit": 0, "free": 0} and me["evidence"]["status"] == "none"
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    assert await candidates(client, s_tokens, journey_id) == []


async def test_the_test_never_shows_the_experts_scores(client, clock, db):
    tokens, _ = await make_teacher(client, clock, db, PHONES[0], tier=0)
    r = await client.get(f"{API}/teachers/me/assessments/tailoring", headers=bearer(tokens))
    assert r.status_code == 200 and len(r.json()["items"]) == 5
    assert "expert_score" not in r.text
    listing = await client.get(f"{API}/teachers/me/assessments", headers=bearer(tokens))
    assert {a["id"] for a in listing.json()["areas"]} == {a["id"] for a in catalog.teacher_tests()["areas"]}
    assert "expert_score" not in listing.text


async def test_passing_the_test_alone_is_not_tier_one(client, clock, db):
    tokens, _ = await make_teacher(client, clock, db, PHONES[0], tier=0)
    r = await client.post(f"{API}/teachers/me/assessments/tailoring/submit", headers=bearer(tokens), json={"scores": perfect_scores("tailoring")})
    body = r.json()
    assert r.status_code == 200 and body["passed"] and body["tier"] == 0 and body["awaiting_evidence"]
    me = (await client.get(f"{API}/teachers/me", headers=bearer(tokens))).json()
    assert me["passed_areas"] == ["tailoring"] and me["tier"] == 0
    assert not any(s["verified"] for s in me["skills"])  # a skill is verified only when both layers are done
    assert "expert_score" not in r.text


async def test_full_path_to_tier_one_through_the_admin(client, clock, db):
    admin = await sign_in(client, clock, ADMIN_PHONE)
    tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], tier=0)
    await client.post(f"{API}/teachers/me/assessments/tailoring/submit", headers=bearer(tokens), json={"scores": perfect_scores("tailoring")})
    r = await client.post(f"{API}/teachers/me/credentials", headers=bearer(tokens), json={"kind": "certificate", "title": "Sewing certificate, ITI Pune", "note": "2019"})
    assert r.status_code == 201 and r.json()["evidence_status"] == "pending"

    queue = (await client.get(f"{API}/admin/teachers/pending", headers=bearer(admin))).json()["teachers"]
    assert [q["teacher_id"] for q in queue] == [teacher_id] and queue[0]["credentials"][0]["title"].startswith("Sewing")
    assert "phone" not in str(queue).lower()

    done = await client.post(f"{API}/admin/teachers/{teacher_id}/verify", headers=bearer(admin), json={"decision": "approve", "note": "Checked the certificate"})
    assert done.status_code == 200 and done.json() == {"teacher_id": teacher_id, "evidence_status": "verified", "tier": 1}
    me = (await client.get(f"{API}/teachers/me", headers=bearer(tokens))).json()
    assert me["tier"] == 1 and me["capacity"] == {"limit": 5, "free": 5}
    assert {s["tag"] for s in me["skills"] if s["verified"]} == {"sewing", "sewing_machine_care", "garment_finishing"}
    assert await db["audit_logs"].count_documents({"action": "teacher_evidence_verified", "ref": teacher_id}) == 1
    assert (await client.get(f"{API}/admin/teachers/pending", headers=bearer(admin))).json()["teachers"] == []


async def test_evidence_first_then_test_also_reaches_tier_one(client, clock, db):
    admin = await sign_in(client, clock, ADMIN_PHONE)
    tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], tier=0)
    await client.post(f"{API}/teachers/me/credentials", headers=bearer(tokens), json={"kind": "experience", "title": "Ten years as a tailor"})
    await client.post(f"{API}/admin/teachers/{teacher_id}/verify", headers=bearer(admin), json={"decision": "approve"})
    assert (await client.get(f"{API}/teachers/me", headers=bearer(tokens))).json()["tier"] == 0  # still needs the test
    r = await client.post(f"{API}/teachers/me/assessments/tailoring/submit", headers=bearer(tokens), json={"scores": perfect_scores("tailoring")})
    assert r.json()["tier"] == 1 and not r.json()["awaiting_evidence"]


async def test_a_rejected_review_keeps_tier_zero_and_can_be_resubmitted(client, clock, db):
    admin = await sign_in(client, clock, ADMIN_PHONE)
    tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], tier=0)
    await client.post(f"{API}/teachers/me/assessments/tailoring/submit", headers=bearer(tokens), json={"scores": perfect_scores("tailoring")})
    await client.post(f"{API}/teachers/me/credentials", headers=bearer(tokens), json={"kind": "reference", "title": "Reference"})
    r = await client.post(f"{API}/admin/teachers/{teacher_id}/verify", headers=bearer(admin), json={"decision": "reject", "note": "Please add a certificate"})
    assert r.json()["tier"] == 0
    me = (await client.get(f"{API}/teachers/me", headers=bearer(tokens))).json()
    assert me["evidence"] == {"status": "rejected", "reviewing": False, "note": "Please add a certificate", "reasons": []}
    again = await client.post(f"{API}/teachers/me/credentials", headers=bearer(tokens), json={"kind": "certificate", "title": "Certificate"})
    assert again.json()["evidence_status"] == "pending"


async def test_only_an_admin_can_review(client, clock, db):
    tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], tier=0)
    await client.post(f"{API}/teachers/me/credentials", headers=bearer(tokens), json={"kind": "certificate", "title": "Certificate"})
    for path, method in ((f"{API}/admin/teachers/pending", "get"), (f"{API}/admin/teachers/{teacher_id}/verify", "post")):
        r = await getattr(client, method)(path, headers=bearer(tokens), **({"json": {"decision": "approve"}} if method == "post" else {}))
        assert r.status_code == 403
    assert (await client.get(f"{API}/admin/teachers/pending")).status_code == 401


async def test_admin_role_comes_only_from_the_setting(client, clock, db):
    plain = await sign_in(client, clock, PHONES[5])
    assert "admin" not in plain["user"]["roles"]
    admin = await sign_in(client, clock, ADMIN_PHONE)
    assert "admin" in admin["user"]["roles"]


async def test_the_test_has_limited_tries_and_needs_every_score(client, clock, db):
    tokens, _ = await make_teacher(client, clock, db, PHONES[0], tier=0)
    url = f"{API}/teachers/me/assessments/tailoring/submit"
    expert = perfect_scores("tailoring")
    wrong = {k: (1 if v >= 3 else 4) for k, v in expert.items()}
    incomplete = await client.post(url, headers=bearer(tokens), json={"scores": {"t1": 3}})
    assert incomplete.status_code == 422 and incomplete.json()["code"] == "scores_incomplete"
    assert (await client.post(url, headers=bearer(tokens), json={"scores": {**expert, "t1": 9}})).status_code == 422
    for left in (2, 1, 0):
        r = await client.post(url, headers=bearer(tokens), json={"scores": wrong})
        assert r.status_code == 200 and not r.json()["passed"] and r.json()["attempts_left"] == left
    blocked = await client.post(url, headers=bearer(tokens), json={"scores": expert})
    assert blocked.status_code == 409 and blocked.json()["code"] == "no_attempts_left"
    assert (await client.get(f"{API}/teachers/me/assessments/tailoring", headers=bearer(tokens))).json()["attempts_left"] == 0


async def test_unknown_area_and_a_student_account(client, clock, db):
    tokens, _ = await make_teacher(client, clock, db, PHONES[0], tier=0)
    assert (await client.get(f"{API}/teachers/me/assessments/nope", headers=bearer(tokens))).status_code == 404
    s_tokens, _, _ = await make_student(client, clock, db, PHONES[1])
    assert (await client.get(f"{API}/teachers/me/assessments", headers=bearer(s_tokens))).status_code == 403
    assert (await client.post(f"{API}/teachers/me/credentials", headers=bearer(s_tokens), json={"kind": "certificate", "title": "x1"})).status_code == 403


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


async def test_only_qualified_mentors_with_a_required_skill_are_offered(client, clock, db):
    await make_teacher(client, clock, db, PHONES[0], tier=1, areas=("tailoring",), name="Tailor")
    await make_teacher(client, clock, db, PHONES[1], tier=1, areas=("house_wiring",), name="Wireman")  # no tailoring skill
    await make_teacher(client, clock, db, PHONES[2], tier=0, name="Unverified")
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[3])
    found = await candidates(client, s_tokens, journey_id)
    assert [c["name"] for c in found] == ["Tailor"]
    assert found[0]["tier"] == 1 and [a["id"] for a in found[0]["verified_in"]] == ["tailoring"] and "skills" not in found[0]


async def test_at_most_three_candidates_nearest_and_best_language_first(client, clock, db):
    await make_teacher(client, clock, db, PHONES[0], name="Far", district="nashik", block="Sinnar", languages=("mr",))
    await make_teacher(client, clock, db, PHONES[1], name="Same block", block="Haveli", languages=("mr",))
    await make_teacher(client, clock, db, PHONES[2], name="Same district", block="Mulshi", languages=("mr",))
    await make_teacher(client, clock, db, PHONES[3], name="Other district Hindi", district="nashik", block="Niphad", languages=("hi",))
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[4])
    await client.patch(f"{API}/me/preferences", headers=bearer(s_tokens), json={"language": "mr"})
    found = await candidates(client, s_tokens, journey_id)
    assert len(found) == 3
    assert [c["name"] for c in found][:2] == ["Same block", "Same district"]
    assert found[0]["same_block"] and found[0]["speaks_your_language"]
    assert "Other district Hindi" not in [c["name"] for c in found]  # lowest: wrong language, wrong district


async def test_candidates_carry_no_phone_or_account_id(client, clock, db):
    await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    r = await client.get(f"{API}/journeys/{journey_id}/match-mentor", headers=bearer(s_tokens))
    user = await db["users"].find_one({"roles": "teacher"})
    assert user["_id"] not in r.text and PHONES[0] not in r.text and "user_id" not in r.text


async def test_a_full_mentor_is_not_offered(client, clock, db):
    _, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    teacher = await db["teacher_profiles"].find_one({"_id": teacher_id})
    for _ in range(5):  # tier 1 holds five learners
        await db["journeys"].insert_one({"_id": uuid.uuid4().hex, "student_id": uuid.uuid4().hex, "teacher_id": teacher["user_id"], "state": "in_progress", "career_id": "tailoring_enterprise"})
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    assert await candidates(client, s_tokens, journey_id) == []
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    assert r.status_code == 409 and r.json()["code"] == "mentor_unavailable"


# ---------------------------------------------------------------------------
# Request, accept, decline, expire
# ---------------------------------------------------------------------------


async def test_request_then_accept_moves_the_journey_to_in_progress(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    request_id = r.json()["id"]

    me = (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()
    assert me["state"] == "mentor_pending" and me["mentor"]["name"] == "Sunita" and me["request"]["status"] == "pending"
    assert (await client.get(f"{API}/teachers/me", headers=bearer(t_tokens))).json()["capacity"]["free"] == 4  # the place is held

    queue = (await client.get(f"{API}/teachers/me/requests", headers=bearer(t_tokens))).json()
    card = queue["pending"][0]["student"]
    assert [p["id"] for p in queue["pending"]] == [request_id]
    assert card["name"] == "Priya" and card["grade"] == 11 and card["career"]["career_id"] == "tailoring_enterprise"
    assert "phone" not in str(card).lower()

    ok = await client.post(f"{API}/requests/{request_id}/accept", headers=bearer(t_tokens))
    assert ok.status_code == 200 and ok.json()["status"] == "accepted"
    me = (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()
    assert me["state"] == "in_progress" and me["mentor"]["teacher_id"] == teacher_id
    students = (await client.get(f"{API}/teachers/me/students", headers=bearer(t_tokens))).json()["students"]
    assert [s["student"]["name"] for s in students] == ["Priya"]
    assert await db["events"].count_documents({"type": "mentor_request_accepted"}) == 1


async def test_the_same_request_twice_is_one_request(client, clock, db):
    _, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    body = {"teacher_id": teacher_id}
    first = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json=body)
    second = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json=body)
    assert second.status_code == 201 and second.json()["id"] == first.json()["id"]
    assert await db["matches"].count_documents({}) == 1


async def test_a_second_mentor_cannot_be_asked_while_one_is_waiting(client, clock, db):
    _, first = await make_teacher(client, clock, db, PHONES[0], name="First")
    _, second = await make_teacher(client, clock, db, PHONES[1], name="Second", block="Mulshi")
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[2])
    await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": first})
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": second})
    assert r.status_code == 409 and r.json()["code"] == "request_pending"
    assert (await client.get(f"{API}/journeys/{journey_id}/match-mentor", headers=bearer(s_tokens))).status_code == 409


async def test_decline_returns_the_learner_to_choose_again_without_that_mentor(client, clock, db):
    t_tokens, declining = await make_teacher(client, clock, db, PHONES[0], name="Declines")
    _, other = await make_teacher(client, clock, db, PHONES[1], name="Other", block="Mulshi")
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[2])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": declining})
    await client.post(f"{API}/requests/{r.json()['id']}/decline", headers=bearer(t_tokens))
    me = (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()
    assert me["state"] == "path_selected" and me["mentor"] is None and me["request"]["status"] == "declined"
    assert [c["name"] for c in await candidates(client, s_tokens, journey_id)] == ["Other"]
    again = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": declining})
    assert again.status_code == 409 and again.json()["code"] == "mentor_unavailable"
    assert (await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": other})).status_code == 201


async def test_an_unanswered_request_lapses_after_48_hours(client, clock, db):
    _, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    clock.advance(47 * 3600)
    s_tokens = await sign_in(client, clock, PHONES[1])  # the 15-minute tokens are long gone
    assert (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()["state"] == "mentor_pending"
    clock.advance(2 * 3600)
    s_tokens = await sign_in(client, clock, PHONES[1])
    t_tokens = await sign_in(client, clock, PHONES[0])
    me = (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()
    assert me["state"] == "path_selected" and me["mentor"] is None and me["request"]["status"] == "expired"
    late = await client.post(f"{API}/requests/{r.json()['id']}/accept", headers=bearer(t_tokens))
    assert late.status_code == 409 and late.json()["code"] == "request_expired"
    assert (await client.get(f"{API}/teachers/me", headers=bearer(t_tokens))).json()["capacity"]["free"] == 5  # the place is released
    assert [c["teacher_id"] for c in await candidates(client, s_tokens, journey_id)] == []  # and the lapsed mentor is not offered again


async def test_the_learner_can_cancel_and_the_place_is_freed(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    c = await client.post(f"{API}/journeys/{journey_id}/mentor-request/cancel", headers=bearer(s_tokens))
    assert c.status_code == 200 and c.json()["status"] == "cancelled"
    assert (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()["state"] == "path_selected"
    assert (await client.get(f"{API}/teachers/me", headers=bearer(t_tokens))).json()["capacity"]["free"] == 5
    late = await client.post(f"{API}/requests/{r.json()['id']}/accept", headers=bearer(t_tokens))
    assert late.status_code == 409 and late.json()["code"] == "already_decided"
    assert (await client.post(f"{API}/journeys/{journey_id}/mentor-request/cancel", headers=bearer(s_tokens))).status_code == 409


async def test_choosing_another_path_cancels_a_waiting_request(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, user_id = await make_student(client, clock, db, PHONES[1])
    await db["assessments"].update_many({"user_id": user_id}, {"$set": {"paths": [{"career_id": "tailoring_enterprise"}, {"career_id": "mobile_repair"}]}})
    await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    assert (await client.post(f"{API}/careers/mobile_repair/select", headers=bearer(s_tokens))).status_code == 201
    queue = (await client.get(f"{API}/teachers/me/requests", headers=bearer(t_tokens))).json()
    assert queue["pending"] == [] and queue["capacity"]["free"] == 5


async def test_requests_are_private_to_their_people(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], name="Owner")
    o_tokens, _ = await make_teacher(client, clock, db, PHONES[1], name="Other teacher", block="Mulshi")
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[2])
    other_student, _, _ = await make_student(client, clock, db, PHONES[3])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    rid = r.json()["id"]
    # another teacher can neither see nor answer it
    assert (await client.get(f"{API}/teachers/me/requests", headers=bearer(o_tokens))).json()["pending"] == []
    for action in ("accept", "decline"):
        assert (await client.post(f"{API}/requests/{rid}/{action}", headers=bearer(o_tokens))).status_code == 404
    # another student cannot see or use this journey
    assert (await client.get(f"{API}/journeys/{journey_id}/match-mentor", headers=bearer(other_student))).status_code == 404
    assert (await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(other_student), json={"teacher_id": teacher_id})).status_code == 404
    assert (await client.post(f"{API}/journeys/{journey_id}/mentor-request/cancel", headers=bearer(other_student))).status_code == 404
    # roles
    assert (await client.post(f"{API}/requests/{rid}/accept", headers=bearer(s_tokens))).status_code == 403
    assert (await client.get(f"{API}/teachers/me/requests", headers=bearer(s_tokens))).status_code == 403


async def test_an_accepted_request_cannot_be_answered_twice(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0])
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    rid = r.json()["id"]
    assert (await client.post(f"{API}/requests/{rid}/accept", headers=bearer(t_tokens))).status_code == 200
    again = await client.post(f"{API}/requests/{rid}/decline", headers=bearer(t_tokens))
    assert again.status_code == 409 and again.json()["code"] == "already_decided"
    assert (await client.get(f"{API}/journeys/me", headers=bearer(s_tokens))).json()["state"] == "in_progress"


async def test_a_young_learner_on_a_hazardous_path_is_flagged_for_the_mentor(client, clock, db):
    t_tokens, teacher_id = await make_teacher(client, clock, db, PHONES[0], areas=("house_wiring",))
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[1], career_id="electrician_wiring", age=16)
    await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": teacher_id})
    card = (await client.get(f"{API}/teachers/me/requests", headers=bearer(t_tokens))).json()["pending"][0]["student"]
    assert card["theory_only"] is True


async def test_an_unknown_mentor_id_is_refused(client, clock, db):
    s_tokens, journey_id, _ = await make_student(client, clock, db, PHONES[0])
    r = await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": "does-not-exist"})
    assert r.status_code == 409 and r.json()["code"] == "mentor_unavailable"
    assert (await client.post(f"{API}/journeys/{journey_id}/mentor-request", headers=bearer(s_tokens), json={"teacher_id": "x"})).status_code == 422
