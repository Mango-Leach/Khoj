"""Rules engine: the three outcomes, and every way it must refuse to guess."""
from __future__ import annotations

from datetime import date

import pytest

from app.services.rules_engine import CHECK, ELIGIBLE, NOT_ELIGIBLE, evaluate, is_placeholder

TODAY = date(2026, 11, 19)


def rule(**over):
    base = {
        "id": "example",
        "source_title": "Official notice",
        "source_url": "https://example.gov.in/notice",
        "entered_on": "2026-11-01",
        "verified_on": None,
        "valid_until": None,
        "docs_required": ["income_certificate"],
        "conditions": [
            {"fact": "grade", "op": "in", "value": [9, 10, 11, 12], "label_i18n": {"en": "Class 9 to 12"}},
            {"fact": "annual_income_inr", "op": "<=", "value": 350000, "label_i18n": {"en": "Income within limit"}},
        ],
    }
    base.update(over)
    return base


def test_eligible_when_every_condition_passes():
    r = evaluate(rule(), {"grade": 10, "annual_income_inr": 200000}, TODAY)
    assert r["status"] == ELIGIBLE
    assert [p["fact"] for p in r["passed"]] == ["grade", "annual_income_inr"]
    assert r["docs_to_prepare"] == ["income_certificate"]


def test_not_eligible_names_the_failed_condition():
    r = evaluate(rule(), {"grade": 10, "annual_income_inr": 900000}, TODAY)
    assert r["status"] == NOT_ELIGIBLE
    assert [f["fact"] for f in r["failed"]] == ["annual_income_inr"]
    assert r["failed"][0]["label"]["en"] == "Income within limit"


def test_missing_fact_is_check_with_office_not_a_guess():
    r = evaluate(rule(), {"grade": 10}, TODAY)
    assert r["status"] == CHECK
    assert [m["fact"] for m in r["missing"]] == ["annual_income_inr"]


def test_a_definite_failure_wins_over_a_missing_fact():
    r = evaluate(rule(), {"grade": 7}, TODAY)
    assert r["status"] == NOT_ELIGIBLE
    assert [m["fact"] for m in r["missing"]] == ["annual_income_inr"]


def test_placeholder_value_is_never_eligible():
    cond = [
        {"fact": "grade", "op": "in", "value": [9, 10], "label_i18n": {}},
        {"fact": "annual_income_inr", "op": "<=", "value": "TODO_VERIFY", "label_i18n": {}},
    ]
    r = evaluate(rule(conditions=cond), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == CHECK
    assert [u["fact"] for u in r["unresolved"]] == ["annual_income_inr"]


def test_placeholder_with_note_and_inside_a_list():
    assert is_placeholder("TODO_VERIFY: income cap")
    assert is_placeholder(["sc", "TODO_VERIFY"])
    assert not is_placeholder(350000)
    assert not is_placeholder("todo later")  # only the exact marker counts


def test_other_condition_failing_still_gives_not_eligible_despite_a_placeholder():
    cond = [
        {"fact": "grade", "op": "in", "value": [9, 10], "label_i18n": {}},
        {"fact": "annual_income_inr", "op": "<=", "value": "TODO_VERIFY", "label_i18n": {}},
    ]
    r = evaluate(rule(conditions=cond), {"grade": 12, "annual_income_inr": 1}, TODAY)
    assert r["status"] == NOT_ELIGIBLE


def test_expired_rule_is_check_with_office_even_if_everything_passes():
    r = evaluate(rule(valid_until="2026-11-18"), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == CHECK
    assert r["expired"] is True


def test_rule_valid_on_its_last_day():
    r = evaluate(rule(valid_until="2026-11-19"), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == ELIGIBLE


def test_unresolved_end_date_is_check_with_office():
    r = evaluate(rule(valid_until="TODO_VERIFY"), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == CHECK


def test_open_ended_rule_has_null_valid_until():
    r = evaluate(rule(valid_until=None), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == ELIGIBLE


def test_stale_record_is_check_with_office():
    r = evaluate(rule(entered_on="2026-01-01"), {"grade": 10, "annual_income_inr": 1}, TODAY, verified_max_days=90)
    assert r["status"] == CHECK
    assert r["stale"] is True


def test_a_human_verification_date_refreshes_a_stale_record():
    r = evaluate(rule(entered_on="2026-01-01", verified_on="2026-11-10"), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == ELIGIBLE
    assert r["verified_on"] == "2026-11-10"
    assert r["awaiting_verification"] is False


def test_awaiting_verification_still_returns_the_real_status():
    r = evaluate(rule(), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == ELIGIBLE
    assert r["awaiting_verification"] is True
    assert r["verified_on"] is None


def test_record_with_no_dates_at_all_is_stale():
    r = evaluate(rule(entered_on=None), {"grade": 10, "annual_income_inr": 1}, TODAY)
    assert r["status"] == CHECK


@pytest.mark.parametrize(
    "op,value,fact,expected",
    [
        ("==", "a", "a", True),
        ("==", "a", "b", False),
        ("!=", "a", "b", True),
        ("<=", 5, 5, True),
        (">=", 5, 4, False),
        ("<", 5, 4, True),
        (">", 5, 5, False),
        ("in", ["a", "b"], "a", True),
        ("not_in", ["a", "b"], "a", False),
        ("not_in", ["a", "b"], "c", True),
    ],
)
def test_every_operator(op, value, fact, expected):
    r = evaluate(rule(conditions=[{"fact": "x", "op": op, "value": value, "label_i18n": {}}]), {"x": fact}, TODAY)
    assert r["status"] == (ELIGIBLE if expected else NOT_ELIGIBLE)


def test_zero_is_a_real_fact_not_a_missing_one():
    r = evaluate(rule(conditions=[{"fact": "annual_income_inr", "op": "<=", "value": 100, "label_i18n": {}}]), {"annual_income_inr": 0}, TODAY)
    assert r["status"] == ELIGIBLE


def test_wrong_type_is_check_with_office_not_a_crash():
    r = evaluate(rule(conditions=[{"fact": "grade", "op": "<=", "value": 12, "label_i18n": {}}]), {"grade": "ten"}, TODAY)
    assert r["status"] == CHECK


def test_unknown_operator_is_check_with_office():
    r = evaluate(rule(conditions=[{"fact": "grade", "op": "~=", "value": 12, "label_i18n": {}}]), {"grade": 10}, TODAY)
    assert r["status"] == CHECK


def test_rule_with_no_conditions_is_not_silently_eligible_for_a_stale_record():
    r = evaluate(rule(conditions=[], entered_on="2020-01-01"), {}, TODAY)
    assert r["status"] == CHECK


def test_source_is_always_returned():
    r = evaluate(rule(), {}, TODAY)
    assert r["source"]["url"] == "https://example.gov.in/notice"
    assert r["source"]["title"] == "Official notice"
