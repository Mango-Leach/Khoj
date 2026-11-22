"""M8: finishing a path, the top 3 opportunities with rule checks, applying, the job pack, and the inbox."""
from __future__ import annotations

import re

import pytest

from app.config import Settings
from app.services import catalog, notifications, opportunities, rules_engine
from tests.conftest import bearer, sign_in
from tests.test_assignments import API, PHONES, make_student, make_teacher, milestones, pair, review, send, template_id, work

C3 = {"c1": 3, "c2": 3, "c3": 3}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_mode=True,
        demo_phones="*",
        jwt_secret="test-secret-0123456789-0123456789-xyz",
        otp_per_ip_per_10min=1000,
        otp_per_phone_per_10min=1000,
        verified_max_days=100000,  # the test clock sits in 2099, so records dated 2026 must not count as old
    )


async def finish_work(client, t, s, jid):
    """The learner does and sends the default assignment of every milestone and the mentor approves each."""
    for key in opportunities.assignments.MILESTONES:
        aid = await template_id(client, s, jid, key)
        sub = await work(client, s, aid)
        assert (await send(client, s, sub["id"])).status_code == 200
        r = await review(client, t, sub["id"], C3)
        assert r.status_code == 200, r.text


async def finished(client, clock, db, phones, career_id="tailoring_enterprise", **profile):
    t, s, jid = await pair(client, clock, db, phones, career_id=career_id, areas=("tailoring", "shop_accounting", "house_wiring", "mobile_repair", "pump_motor", "computer_csc", "digital_marketing"))
    if profile:
        await db["student_profiles"].update_one({"user_id": s["user"]["id"]}, {"$set": profile})
    await finish_work(client, t, s, jid)
    r = await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))
    assert r.status_code == 200, r.text
    return t, s, jid


async def listing(client, s):
    r = await client.get(f"{API}/opportunities", headers=bearer(s))
    assert r.status_code == 200, r.text
    return r.json()


def ids(cards):
    return [c["id"] for c in cards]


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------


def test_the_spec_weights_add_up_to_one():
    assert round(sum(opportunities.WEIGHTS.values()), 6) == 1.0
    assert opportunities.WEIGHTS == {"career_fit": 0.40, "proximity": 0.25, "income_clarity": 0.20, "trust_recency": 0.15}


def test_a_better_fit_scores_higher_and_a_programme_with_no_link_to_the_path_is_not_shown():
    tailoring = catalog.career("tailoring_enterprise")
    by_id = {o["id"]: o for o in catalog.opportunities()}
    assert opportunities.career_fit(by_id["pm_vishwakarma"], tailoring) == (1.0, "your_path")
    assert opportunities.career_fit(by_id["naps"], tailoring) == (1.0, "your_path")  # through its apparel apprenticeship route
    assert opportunities.career_fit(by_id["cmykpy"], tailoring) == (0.4, "any_path")  # open to any path
    assert opportunities.career_fit(by_id["suryamitra"], tailoring) is None  # a solar course has no link to tailoring
    assert opportunities.career_fit(by_id["kvk_training"], tailoring) is None


def test_stipend_beats_support_beats_none_and_unknown_is_lowest():
    clarity = opportunities.INCOME_CLARITY
    assert clarity["stipend"] > clarity["support"] > clarity["none"] > clarity["unknown"]


def test_a_person_verified_record_outranks_an_unverified_one_and_older_records_count_for_less():
    from datetime import date

    today = date(2026, 12, 1)
    fresh = {"entered_on": "2026-11-30", "verified_on": None}
    older = {"entered_on": "2026-09-30", "verified_on": None}
    verified = {"entered_on": "2026-09-30", "verified_on": "2026-11-30"}
    assert opportunities.trust_recency(fresh, today, 90) > opportunities.trust_recency(older, today, 90)
    assert opportunities.trust_recency(verified, today, 90) > opportunities.trust_recency(fresh, today, 90)
    assert opportunities.trust_recency({"entered_on": "2025-01-01", "verified_on": None}, today, 90) == 0.0


def test_every_record_is_complete_cited_and_honest():
    seen_routes = set()
    for opp in catalog.opportunities():
        for key in ("title_i18n", "summary_i18n", "how_i18n"):
            assert set(opp[key]) == {"en", "hi", "mr"}, (opp["id"], key)
        assert opp["income"] in opportunities.INCOME_CLARITY and opp["scope"] in ("national", "state")
        rule = opportunities.rule_of(opp)
        assert rule["source_title"] and rule["source_url"].startswith("https://") and rule["entered_on"], opp["id"]
        # nobody has verified these yet, and nothing here may claim they have
        assert rule.get("verified_on") is None, opp["id"]
        assert opp["apply_url"].startswith("https://")
        for cond in rule["conditions"]:
            assert cond["label_i18n"].get("en"), (opp["id"], cond["fact"])
        seen_routes.update(opp["route_ids"])
    scheme_ids = {o["scheme_id"] for o in catalog.opportunities() if o.get("scheme_id")}
    assert all(catalog.scheme(i) is not None for i in scheme_ids)
    # every route a career names that has a record is reachable, and every career has at least two places to go
    for career in catalog.careers():
        reachable = [o for o in catalog.opportunities() if opportunities.career_fit(o, career) is not None]
        assert len(reachable) >= 2, career["career_id"]


def test_no_opportunity_text_states_a_pay_or_loan_figure():
    money = re.compile(r"₹|\bRs\b|rupee|lakh|crore|\bINR\b", re.IGNORECASE)
    for opp in catalog.opportunities():
        for key in ("title_i18n", "summary_i18n", "how_i18n"):
            assert not money.search(opp[key]["en"]), (opp["id"], key)


def test_a_notification_keeps_only_short_plain_values():
    cleaned = notifications._clean_params({"result": "approved", "n": 3, "note": "x" * 500, "bad": {"a": 1}})
    assert cleaned == {"result": "approved", "n": "3", "note": "x" * 60}


# ---------------------------------------------------------------------------
# Finishing the path
# ---------------------------------------------------------------------------


async def test_a_learner_cannot_finish_before_every_milestone_is_approved(client, clock, db):
    t, s, jid = await pair(client, clock, db, PHONES[0:2])
    r = await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "milestones_not_done"
    aid = await template_id(client, s, jid, "explore")
    sub = await work(client, s, aid)
    await send(client, s, sub["id"])
    await review(client, t, sub["id"], C3)  # one milestone of three
    assert (await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))).json()["code"] == "milestones_not_done"


async def test_without_a_mentor_the_path_cannot_be_finished(client, clock, db):
    s, jid = await make_student(client, clock, db, PHONES[2])
    r = await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "mentor_required"


async def test_finishing_opens_the_path_once_and_tells_the_learner_once(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[3:5])
    again = await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))
    assert again.status_code == 200 and again.json()["state"] == "opportunities_open"
    journey = await db["journeys"].find_one({"_id": jid})
    assert journey["state"] == "opportunities_open" and journey["completed_at"] and journey["opportunities_open_at"]
    inbox = (await client.get(f"{API}/notifications", headers=bearer(s))).json()["items"]
    assert [n["kind"] for n in inbox].count("path_complete") == 1
    assert await db["events"].count_documents({"type": "journey_completed"}) == 1
    # the mentor's slot is free again
    assert (await client.get(f"{API}/teachers/me/students", headers=bearer(t))).json()["students"] == []


async def test_a_learner_cannot_finish_someone_elses_journey(client, clock, db):
    t, s, jid = await pair(client, clock, db, PHONES[5:7])
    other, _ = await make_student(client, clock, db, PHONES[7])
    assert (await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(other))).status_code == 404
    assert (await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(t))).status_code == 403


async def test_a_high_risk_trade_says_a_person_must_check_the_work_in_person(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[8:10], career_id="electrician_wiring")
    data = await listing(client, s)
    assert data["in_person_check_needed"] is True
    safe = await finished(client, clock, db, PHONES[10:12])
    assert (await listing(client, safe[1]))["in_person_check_needed"] is False


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------


async def test_the_top_three_are_ranked_by_score_with_sources_and_no_link_means_not_shown(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[12:14])
    data = await listing(client, s)
    assert len(data["top"]) == 3
    scores = [c["score"] for c in data["top"]]
    assert scores == sorted(scores, reverse=True)
    shown = set(ids(data["top"]) + ids(data["more"]) + ids(data["not_yet"]))
    assert "pm_vishwakarma" in shown and "naps" in shown
    assert not shown & {"suryamitra", "kvk_training", "mpsc", "csc_vle"}  # no link to tailoring
    for card in data["top"] + data["more"]:
        assert card["source"]["url"].startswith("https://") and card["source"]["entered_on"]
        assert card["source"]["awaiting_verification"] is True  # nobody has verified these yet
        assert card["reasons"] and card["how"]["en"] and card["apply_url"]


async def test_a_rule_a_learner_definitely_fails_is_never_in_the_top_and_says_when_it_opens(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[14:16])  # a 17 year old; PM Vishwakarma needs 18
    data = await listing(client, s)
    assert "pm_vishwakarma" not in ids(data["top"] + data["more"])
    card = next(c for c in data["not_yet"] if c["id"] == "pm_vishwakarma")
    assert card["eligibility"]["status"] == rules_engine.NOT_ELIGIBLE
    assert card["eligibility"]["opens_at"] == [{"fact": "age", "value": 18}]
    # and she cannot register interest in it
    r = await client.post(f"{API}/opportunities/pm_vishwakarma/apply", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "not_eligible"


async def test_nothing_with_an_unconfirmed_rule_is_ever_shown_as_eligible(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[16:18], career_id="mobile_repair")
    data = await listing(client, s)
    for card in data["top"] + data["more"]:
        if card["eligibility"]["unresolved"] or card["eligibility"]["missing"]:
            assert card["eligibility"]["status"] == rules_engine.CHECK, card["id"]


async def test_a_learner_who_meets_every_stated_rule_sees_eligible_with_the_papers_to_bring(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[18:20], career_id="shop_accounting_gst", age=20, grade=14)
    data = await listing(client, s)
    csc = next(c for c in data["top"] + data["more"] if c["id"] == "csc_vle")
    assert csc["eligibility"]["status"] == rules_engine.ELIGIBLE
    assert "aadhaar" in csc["docs"]
    nats = next(c for c in data["top"] + data["more"] if c["id"] == "nats")
    assert nats["eligibility"]["status"] == rules_engine.CHECK  # it needs a qualification, which the learner has not told us
    assert "qualification" in data["ask"]


async def test_answers_for_a_check_change_the_result_and_are_not_stored(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[20:22], career_id="shop_accounting_gst", age=20, grade=14)
    r = await client.post(f"{API}/opportunities/check", headers=bearer(s), json={"facts": {"qualification": "graduate"}})
    assert r.status_code == 200
    nats = next(c for c in r.json()["top"] + r.json()["more"] if c["id"] == "nats")
    assert "qualification" not in [m["fact"] for m in nats["eligibility"]["missing"]]
    profile = await db["student_profiles"].find_one({"user_id": s["user"]["id"]})
    assert "qualification" not in profile
    # an answer can never change the age or class the profile holds
    r = await client.post(f"{API}/opportunities/check", headers=bearer(s), json={"facts": {"qualification": "graduate"}})
    assert r.status_code == 200
    bad = await client.post(f"{API}/opportunities/check", headers=bearer(s), json={"facts": {"age": 99}})
    assert bad.status_code == 422


async def test_a_programme_past_its_deadline_is_dropped(client, clock, db, monkeypatch):
    records = [dict(o) for o in catalog.opportunities()]
    for o in records:
        if o["id"] == "naps":
            o["deadline"] = "2000-01-01"
    monkeypatch.setattr(catalog, "opportunities", lambda: records)
    t, s, jid = await finished(client, clock, db, PHONES[22:24])
    data = await listing(client, s)
    assert "naps" not in ids(data["top"] + data["more"] + data["not_yet"])


async def test_an_expired_record_drops_out_of_the_top_and_says_to_check_the_source(client, clock, db, monkeypatch):
    records = [dict(o) for o in catalog.opportunities()]
    for o in records:
        if o["id"] == "cmykpy":
            o["valid_until"] = "2000-01-01"
    monkeypatch.setattr(catalog, "opportunities", lambda: records)
    t, s, jid = await finished(client, clock, db, PHONES[24:26], age=20, grade=14)
    data = await listing(client, s)
    assert "cmykpy" not in ids(data["top"])
    card = next(c for c in data["more"] if c["id"] == "cmykpy")
    assert card["eligibility"]["expired"] is True and card["eligibility"]["status"] == rules_engine.CHECK


async def test_a_learner_who_started_another_path_still_has_the_finished_one(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[26:28])
    clock.advance(60)  # the newest assessment wins, so it must be later than the first
    await db["assessments"].insert_one({"_id": "a2", "user_id": s["user"]["id"], "created_at": clock.now, "based_on": {"skills": []}, "paths": [{"career_id": "dairy_poultry"}]})
    assert (await client.post(f"{API}/careers/dairy_poultry/select", headers=bearer(s))).status_code == 201
    assert (await db["journeys"].find_one({"_id": jid}))["state"] == "opportunities_open"
    assert len((await listing(client, s))["top"]) == 3


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


async def test_applying_is_a_record_of_interest_and_asking_twice_is_one_application(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[0:2], age=20, grade=12)
    first = await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))
    again = await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))
    assert first.status_code == 201 and again.status_code == 201
    assert first.json()["application"]["id"] == again.json()["application"]["id"]
    assert first.json()["application"]["status"] == "interested"
    assert await db["applications"].count_documents({}) == 1
    data = await listing(client, s)
    assert next(c for c in data["top"] + data["more"] if c["id"] == "naps")["application"]["status"] == "interested"
    assert (await client.post(f"{API}/opportunities/nope/apply", headers=bearer(s))).status_code == 404


async def test_the_mentor_is_told_and_marks_their_help_but_cannot_apply_or_confirm(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[2:4], age=20, grade=12)
    app_id = (await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))).json()["application"]["id"]
    kinds = [n["kind"] for n in (await client.get(f"{API}/notifications", headers=bearer(t))).json()["items"]]
    assert "help_apply" in kinds
    waiting = (await client.get(f"{API}/teachers/me/applications", headers=bearer(t))).json()["applications"]
    assert [a["id"] for a in waiting] == [app_id] and waiting[0]["student"]["name"] == "Priya"

    stranger, _ = await make_teacher(client, clock, db, PHONES[4])
    assert (await client.post(f"{API}/applications/{app_id}/assist", headers=bearer(stranger))).status_code == 404
    assert (await client.post(f"{API}/applications/{app_id}/assist", headers=bearer(s))).status_code == 403  # a learner
    helped = await client.post(f"{API}/applications/{app_id}/assist", headers=bearer(t))
    assert helped.status_code == 200 and helped.json()["application"]["status"] == "mentor_assisted"
    assert (await client.post(f"{API}/applications/{app_id}/assist", headers=bearer(t))).json()["application"]["status"] == "mentor_assisted"
    assert "mentor_helped" in [n["kind"] for n in (await client.get(f"{API}/notifications", headers=bearer(s))).json()["items"]]
    # there is no call a mentor can use to set applied or confirmed
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(t), json={"status": "confirmed"})).status_code == 403
    assert (await client.get(f"{API}/teachers/me/applications", headers=bearer(t))).json()["applications"][0]["status"] == "mentor_assisted"


async def test_only_the_learner_confirms_and_the_steps_go_in_order(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[5:7], age=20, grade=12)
    app_id = (await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))).json()["application"]["id"]
    skip = await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "confirmed"})
    assert skip.status_code == 409 and skip.json()["code"] == "bad_step"  # not before they have applied
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "applied"})).json()["application"]["status"] == "applied"
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "applied"})).status_code == 200  # the same answer twice
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "mentor_assisted"})).status_code == 422
    done = await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "confirmed"})
    assert done.json()["application"]["status"] == "confirmed"
    assert (await db["journeys"].find_one({"_id": jid}))["state"] == "enrolled"
    history = (await db["applications"].find_one({"_id": app_id}))["history"]
    assert [h["status"] for h in history] == ["interested", "applied", "confirmed"] and all(h["by"] == "student" for h in history)
    # a confirmed application is final, and the list is still open
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "withdrawn"})).status_code == 409
    assert len((await listing(client, s))["top"]) == 3


async def test_nobody_else_can_touch_a_learners_application(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[7:9], age=20, grade=12)
    app_id = (await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))).json()["application"]["id"]
    other, _ = await make_student(client, clock, db, PHONES[9])
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(other), json={"status": "applied"})).status_code == 404
    assert (await client.get(f"{API}/applications/me", headers=bearer(other))).json()["applications"] == []
    assert len((await client.get(f"{API}/applications/me", headers=bearer(s))).json()["applications"]) == 1


async def test_a_withdrawn_application_can_be_asked_for_again(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[10:12], age=20, grade=12)
    app_id = (await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))).json()["application"]["id"]
    assert (await client.patch(f"{API}/applications/{app_id}", headers=bearer(s), json={"status": "withdrawn"})).json()["application"]["status"] == "withdrawn"
    again = await client.post(f"{API}/opportunities/naps/apply", headers=bearer(s))
    assert again.json()["application"]["id"] == app_id and again.json()["application"]["status"] == "interested"


async def test_applying_needs_a_chosen_path_and_a_visible_opportunity(client, clock, db):
    lone = await sign_in(client, clock, PHONES[14])  # a learner with a profile who has not picked a path
    assert (await client.post(f"{API}/students/profile", headers=bearer(lone), json={"name": "Amit", "age": 19, "grade": 12, "district": "pune", "block": "Haveli", "guardian_consent": False})).status_code == 201
    assert (await client.get(f"{API}/opportunities", headers=bearer(lone))).json()["code"] == "no_path"
    t, s, jid = await pair(client, clock, db, PHONES[12:14])
    data = await listing(client, s)
    hidden = [o["id"] for o in catalog.opportunities() if o["id"] not in ids(data["top"] + data["more"])]
    r = await client.post(f"{API}/opportunities/{hidden[0]}/apply", headers=bearer(s))
    assert r.status_code == 409 and r.json()["code"] == "opp_locked"


# ---------------------------------------------------------------------------
# Previews before the path is finished
# ---------------------------------------------------------------------------


async def approve_milestone(client, t, s, jid, number):
    """The mentor approves the learner's work for milestone `number` (1 to 3)."""
    key = opportunities.assignments.MILESTONES[number - 1]
    sub = await work(client, s, await template_id(client, s, jid, key))
    assert (await send(client, s, sub["id"])).status_code == 200
    assert (await review(client, t, sub["id"], C3)).status_code == 200


async def test_two_previews_at_the_start_then_more_as_a_mentor_approves_work(client, clock, db, monkeypatch):
    # the seeded list is short, so add copies of one open-to-any-path programme to see all four levels
    base = next(o for o in catalog.opportunities() if o["id"] == "mahaswayam_rojgar")
    records = [dict(o) for o in catalog.opportunities()] + [{**base, "id": f"extra_{n}"} for n in range(5)]
    monkeypatch.setattr(catalog, "opportunities", lambda: records)
    t, s, jid = await pair(client, clock, db, PHONES[15:17], career_id="shop_accounting_gst", areas=("shop_accounting",))
    await db["student_profiles"].update_one({"user_id": s["user"]["id"]}, {"$set": {"age": 20, "grade": 14}})  # old enough for most programmes
    steps = []
    for approved in range(4):
        if approved:
            await approve_milestone(client, t, s, jid, approved)
        steps.append(await listing(client, s))
    assert (await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))).status_code == 200
    full = await listing(client, s)
    every = ids(full["top"] + full["more"])
    assert len(every) > 6  # there is something left to unlock
    for approved, (data, shown) in enumerate(zip(steps, (2, 3, 6, 6))):
        got = ids(data["top"] + data["more"])
        assert got == every[:shown], approved  # the best ones first, and each unlock keeps what was shown
        assert len(data["top"]) == min(3, shown)
        assert data["unlock"]["approved"] == approved and data["unlock"]["finished"] is False
        assert data["unlock"]["locked"] == len(every) - shown
        assert data["not_yet"] == []  # these wait for the finish


async def test_a_hidden_programme_is_never_sent_and_cannot_be_asked_for(client, clock, db):
    t, s, jid = await pair(client, clock, db, PHONES[17:19])
    data = await listing(client, s)
    sent = ids(data["top"] + data["more"])
    full = await finished(client, clock, db, PHONES[19:21])
    rest = ids((await listing(client, full[1]))["top"] + (await listing(client, full[1]))["more"])
    hidden = [i for i in rest if i not in sent]
    assert hidden and len(sent) == 2
    for card in data["top"] + data["more"]:
        assert card["id"] not in hidden
    assert (await client.post(f"{API}/opportunities/{hidden[0]}/apply", headers=bearer(s))).json()["code"] == "opp_locked"
    shown = await client.post(f"{API}/opportunities/{sent[0]}/apply", headers=bearer(s))
    assert shown.status_code == 201  # one that was shown can be asked for


async def test_interest_in_a_preview_reaches_the_mentor_who_is_still_guiding(client, clock, db):
    t, s, jid = await pair(client, clock, db, PHONES[21:23], areas=("tailoring",))
    await db["student_profiles"].update_one({"user_id": s["user"]["id"]}, {"$set": {"age": 20, "grade": 12}})
    first = ids((await listing(client, s))["top"])[0]
    made = await client.post(f"{API}/opportunities/{first}/apply", headers=bearer(s))
    assert made.status_code == 201, made.text
    waiting = (await client.get(f"{API}/teachers/me/applications", headers=bearer(t))).json()["applications"]
    assert [a["opportunity_id"] for a in waiting] == [first]


async def test_finishing_opens_everything_including_those_not_open_yet(client, clock, db):
    t, s, jid = await finished(client, clock, db, PHONES[23:25])
    data = await listing(client, s)
    assert {k: data["unlock"][k] for k in ("finished", "approved", "total", "locked")} == {"finished": True, "approved": 3, "total": 3, "locked": 0}
    assert len(data["top"]) == 3 and data["not_yet"]


async def test_a_learner_without_a_mentor_sees_two_previews_and_is_told_a_mentor_is_needed(client, clock, db):
    s, jid = await make_student(client, clock, db, PHONES[25])
    data = await listing(client, s)
    assert len(data["top"]) == 2 and data["more"] == []
    assert data["unlock"]["has_mentor"] is False and data["unlock"]["approved"] == 0


# ---------------------------------------------------------------------------
# The job pack
# ---------------------------------------------------------------------------


async def test_the_job_pack_opens_only_after_the_path_is_finished_and_cites_its_sources(client, clock, db):
    t, s, jid = await pair(client, clock, db, PHONES[14:16])
    locked = await client.get(f"{API}/careers/tailoring_enterprise/pack", headers=bearer(s))
    assert locked.status_code == 409 and locked.json()["code"] == "pack_locked"
    await finish_work(client, t, s, jid)
    await client.post(f"{API}/journeys/{jid}/complete", headers=bearer(s))
    pack = (await client.get(f"{API}/careers/tailoring_enterprise/pack", headers=bearer(s))).json()
    assert {x["opportunity_id"] for x in pack["steps"]} >= {"pm_vishwakarma", "naps"}
    order = [x["opportunity_id"] for x in pack["steps"]]
    assert order.index("naps") < order.index("cmykpy") and order.index("pm_vishwakarma") < order.index("mahaswayam_rojgar")  # made for the path first
    assert all(x["source"]["url"].startswith("https://") for x in pack["steps"])
    assert pack["pitch"] and pack["courses"] is not None and "aadhaar" in pack["documents"]["usual"]
    assert pack["safety"] == {"class": "low", "in_person_check_needed": False}
    # a path the learner did not finish stays closed
    assert (await client.get(f"{API}/careers/dairy_poultry/pack", headers=bearer(s))).json()["code"] == "pack_locked"
    assert (await client.get(f"{API}/careers/nonsense/pack", headers=bearer(s))).status_code == 404


# ---------------------------------------------------------------------------
# The inbox
# ---------------------------------------------------------------------------


async def test_the_inbox_follows_the_mentoring_loop_and_each_message_has_a_link(client, clock, db):
    t, tid = await make_teacher(client, clock, db, PHONES[16])
    s, jid = await make_student(client, clock, db, PHONES[17])
    r = await client.post(f"{API}/journeys/{jid}/mentor-request", headers=bearer(s), json={"teacher_id": tid})
    teacher_inbox = (await client.get(f"{API}/notifications", headers=bearer(t))).json()
    assert [n["kind"] for n in teacher_inbox["items"]] == ["mentor_request"] and teacher_inbox["unread"] == 1
    assert teacher_inbox["items"][0]["link"] == "/t/requests"
    await client.post(f"{API}/requests/{r.json()['id']}/accept", headers=bearer(t))
    student_inbox = (await client.get(f"{API}/notifications", headers=bearer(s))).json()["items"]
    assert [n["kind"] for n in student_inbox] == ["mentor_accepted"]
    aid = await template_id(client, s, jid, "explore")
    sub = await work(client, s, aid)
    await send(client, s, sub["id"])
    await send(client, s, sub["id"])  # sent twice, told once
    kinds = [n["kind"] for n in (await client.get(f"{API}/notifications", headers=bearer(t))).json()["items"]]
    assert kinds.count("work_sent") == 1
    await review(client, t, sub["id"], C3)
    ready = [n for n in (await client.get(f"{API}/notifications", headers=bearer(s))).json()["items"] if n["kind"] == "review_ready"]
    assert len(ready) == 1 and ready[0]["params"] == {"result": "approved"} and ready[0]["link"] == f"/assignments/{aid}"


async def test_messages_hold_no_names_or_free_text(client, clock, db):
    t, tid = await make_teacher(client, clock, db, PHONES[18], name="Sunita Kulkarni")
    s, jid = await make_student(client, clock, db, PHONES[19], name="Zubeida Qureshi")
    await client.post(f"{API}/journeys/{jid}/mentor-request", headers=bearer(s), json={"teacher_id": tid})
    stored = [d async for d in db["notifications"].find({})]
    text = repr(stored)
    assert stored and "Zubeida" not in text and "Qureshi" not in text and "Sunita" not in text


async def test_reading_marks_a_message_read_and_nobody_reads_anothers(client, clock, db):
    t, tid = await make_teacher(client, clock, db, PHONES[20])
    s, jid = await make_student(client, clock, db, PHONES[21])
    await client.post(f"{API}/journeys/{jid}/mentor-request", headers=bearer(s), json={"teacher_id": tid})
    item = (await client.get(f"{API}/notifications", headers=bearer(t))).json()["items"][0]
    assert (await client.post(f"{API}/notifications/{item['id']}/read", headers=bearer(s))).status_code == 404
    assert (await client.get(f"{API}/notifications/unread", headers=bearer(s))).json() == {"unread": 0}
    done = await client.post(f"{API}/notifications/{item['id']}/read", headers=bearer(t))
    assert done.json()["unread"] == 0 and done.json()["notification"]["read"] is True
    assert (await client.post(f"{API}/notifications/{item['id']}/read", headers=bearer(t))).status_code == 200  # twice is fine
    assert (await client.get(f"{API}/notifications", headers=bearer(t))).json()["unread"] == 0


async def test_read_all_clears_the_count(client, clock, db):
    t, tid = await make_teacher(client, clock, db, PHONES[22])
    for n in range(3):
        await notifications.notify(db, (await db["teacher_profiles"].find_one({"_id": tid}))["user_id"], "mentor_request", "/t/requests")
    assert (await client.get(f"{API}/notifications/unread", headers=bearer(t))).json() == {"unread": 3}
    assert (await client.post(f"{API}/notifications/read-all", headers=bearer(t))).json() == {"unread": 0}


async def test_an_unknown_kind_is_refused_and_the_same_key_is_stored_once(db):
    with pytest.raises(ValueError):
        await notifications.notify(db, "u1", "something_else", "/home")
    assert await notifications.notify(db, "u1", "mentor_request", "/t/requests", dedupe_key="k") is True
    assert await notifications.notify(db, "u1", "mentor_request", "/t/requests", dedupe_key="k") is False
    assert await db["notifications"].count_documents({}) == 1
