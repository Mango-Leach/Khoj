"""Scheme rules (M4): the data files, and the check API."""
from __future__ import annotations

import copy
from datetime import date

import pytest

from app.services import catalog, rules_engine, schemes
from tests.conftest import STUDENT, TEACHER, bearer, sign_in

API = "/api/v1"
IDS = {"pms_sc_maharashtra", "ebc_shahu_maharashtra", "nmmss", "pm_yasasvi", "pm_vishwakarma", "pmkvy", "naps", "nats"}


# --- data ----------------------------------------------------------------------


def test_there_are_exactly_the_eight_schemes():
    assert {s["id"] for s in catalog.schemes()} == IDS


@pytest.mark.parametrize("scheme", catalog.schemes(), ids=lambda s: s["id"])
def test_every_scheme_cites_an_official_source_and_is_awaiting_a_human(scheme):
    assert scheme["source_title"].strip() and scheme["source_url"].startswith("https://")
    assert any(h in scheme["source_url"] for h in (".gov.in", ".nic.in")), "an official domain"
    assert scheme["entered_on"] == "2026-11-19"
    assert scheme["verified_on"] is None, "only a person may set verified_on"
    assert scheme["verification_status"] == "awaiting_verification"
    assert scheme["name_i18n"]["en"] and scheme["research_note"]
    for cond in scheme["conditions"]:
        assert cond["op"] in rules_engine._OPS
        assert cond["label_i18n"]["en"]


@pytest.mark.parametrize("scheme", catalog.schemes(), ids=lambda s: s["id"])
def test_a_scheme_with_a_placeholder_is_never_eligible(scheme):
    """The acceptance rule: no scheme shows Eligible while a needed value is still TODO_VERIFY."""
    placeholder = rules_engine.is_placeholder(scheme.get("valid_until")) or any(
        rules_engine.is_placeholder(c["value"]) for c in scheme["conditions"]
    )
    if not placeholder:
        pytest.skip("no placeholder in this scheme")
    # give every condition a value that passes, as far as the real values allow
    facts = {}
    for c in scheme["conditions"]:
        v = c["value"]
        if rules_engine.is_placeholder(v):
            facts[c["fact"]] = "anything"
        elif c["op"] in ("in",):
            facts[c["fact"]] = v[0]
        elif c["op"] in (">=", "<=", "=="):
            facts[c["fact"]] = v
    fresh = copy.deepcopy(scheme)
    fresh["entered_on"] = "2026-11-19"
    r = rules_engine.evaluate(fresh, facts, date(2026, 11, 20), 90)
    assert r["status"] != rules_engine.ELIGIBLE


def test_each_scheme_condition_fact_is_known_or_a_placeholder():
    known = set(schemes.PROFILE_FACTS) | set(schemes.ASK_ORDER)
    for s in catalog.schemes():
        for c in s["conditions"]:
            assert c["fact"] in known or rules_engine.is_placeholder(c["value"]), (s["id"], c["fact"])


def test_no_scheme_asks_for_income_unless_it_has_an_income_limit():
    for s in catalog.schemes():
        has_limit = any(c["fact"] == "annual_income_inr" for c in s["conditions"])
        assert ("annual_income_inr" in schemes.needs(s)) == has_limit


def test_the_real_records_go_stale_when_nobody_verifies_them():
    s = catalog.scheme("pm_vishwakarma")
    facts = {"age": 20, "state": "maharashtra", "works_in_listed_trade": True, "govt_service_in_family": False, "took_similar_loan_5y": False}
    assert rules_engine.evaluate(s, facts, date(2026, 11, 20), 90)["status"] == rules_engine.ELIGIBLE
    assert rules_engine.evaluate(s, facts, date(2027, 6, 1), 90)["status"] == rules_engine.CHECK


# --- API -----------------------------------------------------------------------


@pytest.fixture
def fresh(monkeypatch):
    """The test clock sits in 2099, so every real record would be stale. Make them look just entered."""
    rules = copy.deepcopy(catalog.schemes())
    for s in rules:
        s["entered_on"] = "2099-01-01"
    monkeypatch.setattr(catalog, "schemes", lambda: rules)
    return rules


async def student(client, clock, profile=STUDENT, phone="9876543210"):
    tokens = await sign_in(client, clock, phone)
    r = await client.post(f"{API}/students/profile", json=profile, headers=bearer(tokens))
    assert r.status_code == 201, r.text
    return tokens


async def check(client, tokens, facts=None, ids=None):
    body = {"facts": facts or {}}
    if ids is not None:
        body["scheme_ids"] = ids
    return await client.post(f"{API}/scholarships/check", json=body, headers=bearer(tokens))


def by_id(data):
    return {r["id"]: r for r in data["results"]}


async def test_list_shows_every_scheme_with_source_and_awaiting_label(client, clock):
    tokens = await student(client, clock)
    r = await client.get(f"{API}/scholarships", headers=bearer(tokens))
    assert r.status_code == 200
    items = r.json()["schemes"]
    assert {i["id"] for i in items} == IDS
    for i in items:
        assert i["source"]["url"].startswith("https://") and i["source"]["title"]
        assert i["source"]["awaiting_verification"] is True and i["source"]["verified_on"] is None
        assert "status" not in i  # eligibility needs the check


async def test_a_minor_is_not_eligible_for_pm_vishwakarma_and_sees_when_it_opens(client, clock, fresh):
    tokens = await student(client, clock)  # age 16
    r = await check(client, tokens, {"works_in_listed_trade": True, "govt_service_in_family": False, "took_similar_loan_5y": False})
    v = by_id(r.json())["pm_vishwakarma"]
    assert v["status"] == "not_eligible"
    assert v["opens_at"] == [{"fact": "age", "value": 18}]
    assert v["failed"][0]["label"]["en"] == "Aged 18 or more"


async def test_an_adult_tailor_is_eligible_for_pm_vishwakarma(client, clock, fresh):
    tokens = await student(client, clock, {**STUDENT, "age": 20, "grade": 14, "guardian_consent": False})
    r = await check(client, tokens, {"works_in_listed_trade": True, "govt_service_in_family": False, "took_similar_loan_5y": False})
    v = by_id(r.json())["pm_vishwakarma"]
    assert v["status"] == "eligible"
    assert v["source"]["awaiting_verification"] is True  # the label stays until a person verifies


async def test_one_scheme_shows_each_of_the_three_outcomes(client, clock, fresh):
    tokens = await student(client, clock, {**STUDENT, "grade": 12})
    ok = by_id((await check(client, tokens, {"social_category": "sc", "annual_income_inr": 200000})).json())["pms_sc_maharashtra"]
    no = by_id((await check(client, tokens, {"social_category": "sc", "annual_income_inr": 900000})).json())["pms_sc_maharashtra"]
    unsure = by_id((await check(client, tokens, {"social_category": "sc"})).json())["pms_sc_maharashtra"]
    assert (ok["status"], no["status"], unsure["status"]) == ("eligible", "not_eligible", "check_with_office")
    assert [f["fact"] for f in no["failed"]] == ["annual_income_inr"]
    assert [m["fact"] for m in unsure["missing"]] == ["annual_income_inr"]


async def test_nothing_is_eligible_when_a_value_is_a_placeholder(client, clock, fresh):
    tokens = await student(client, clock, {**STUDENT, "grade": 10})
    facts = {"social_category": "obc", "annual_income_inr": 100000, "school_type": "government"}
    data = by_id((await check(client, tokens, facts)).json())
    for sid in ("nmmss", "pm_yasasvi", "pmkvy", "naps", "nats"):
        assert data[sid]["status"] != "eligible", sid
    assert data["nmmss"]["unresolved"], "the open question is shown"


async def test_the_income_check_asks_only_for_schemes_that_need_it(client, clock, fresh):
    tokens = await student(client, clock)
    r = (await check(client, tokens, ids=["pm_vishwakarma"])).json()
    assert "annual_income_inr" not in r["ask"] and "social_category" not in r["ask"]
    assert set(r["ask"]) <= {"works_in_listed_trade", "govt_service_in_family", "took_similar_loan_5y"}


async def test_results_are_ordered_eligible_then_check_then_not_eligible(client, clock, fresh):
    tokens = await student(client, clock, {**STUDENT, "age": 20, "grade": 12, "guardian_consent": False})
    facts = {"social_category": "sc", "annual_income_inr": 100000, "works_in_listed_trade": True, "govt_service_in_family": False, "took_similar_loan_5y": False}
    results = (await check(client, tokens, facts)).json()["results"]
    order = [{"eligible": 0, "check_with_office": 1, "not_eligible": 2}[r["status"]] for r in results]
    assert order == sorted(order)


async def test_papers_to_prepare_follow_the_questions_asked(client, clock, fresh):
    tokens = await student(client, clock, {**STUDENT, "grade": 12})
    v = by_id((await check(client, tokens, {"social_category": "sc", "annual_income_inr": 100000})).json())["pms_sc_maharashtra"]
    assert set(v["docs"]) == {"income_certificate", "category_certificate"}


async def test_the_learners_answers_are_not_stored(client, clock, db, fresh):
    tokens = await student(client, clock, {**STUDENT, "grade": 12})
    await check(client, tokens, {"social_category": "sc", "annual_income_inr": 123457})
    for name in await db.list_collection_names():
        async for doc in db[name].find({}):
            assert "123457" not in str(doc), name


async def test_the_body_cannot_override_age_or_class(client, clock, fresh):
    tokens = await student(client, clock)
    r = await client.post(f"{API}/scholarships/check", json={"facts": {"age": 30}}, headers=bearer(tokens))
    assert r.status_code == 422


async def test_unknown_scheme_and_bad_values_are_refused(client, clock, fresh):
    tokens = await student(client, clock)
    assert (await check(client, tokens, ids=["nope"])).status_code == 404
    assert (await check(client, tokens, {"annual_income_inr": -5})).status_code == 422
    assert (await check(client, tokens, {"social_category": "martian"})).status_code == 422


async def test_check_is_for_signed_in_students_only(client, clock, fresh):
    assert (await client.post(f"{API}/scholarships/check", json={})).status_code == 401
    assert (await client.get(f"{API}/scholarships")).status_code == 401
    new_user = await sign_in(client, clock)  # signed in, no student profile yet, so no student role
    assert (await check(client, new_user)).status_code == 403
    teacher = await sign_in(client, clock, "9123456789")
    assert (await client.post(f"{API}/teachers/profile", json=TEACHER, headers=bearer(teacher))).status_code == 201
    assert (await check(client, teacher)).status_code == 403
    assert (await client.get(f"{API}/scholarships", headers=bearer(teacher))).status_code == 403


async def test_a_verified_rule_loses_the_awaiting_label(client, clock, fresh):
    for s in fresh:
        if s["id"] == "pm_vishwakarma":
            s["verified_on"] = "2099-01-02"
    tokens = await student(client, clock)
    v = by_id((await check(client, tokens)).json())["pm_vishwakarma"]
    assert v["source"]["awaiting_verification"] is False and v["source"]["verified_on"] == "2099-01-02"


async def test_translations_are_attached_and_labelled_when_they_exist(client, clock, fresh, monkeypatch):
    i18n = {"pm_vishwakarma": {"hi": {"name": "पीएम विश्वकर्मा", "conditions": ["18 साल या ज़्यादा"]}}}
    monkeypatch.setattr(catalog, "schemes_i18n", lambda: i18n)
    tokens = await student(client, clock)
    v = by_id((await check(client, tokens)).json())["pm_vishwakarma"]
    assert v["name"]["hi"] == "पीएम विश्वकर्मा" and v["name"]["en"]
    assert v["machine_translated"] == ["hi"]
    assert v["failed"][0]["label"]["hi"] == "18 साल या ज़्यादा"
