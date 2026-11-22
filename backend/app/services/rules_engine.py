"""Scheme-as-code rules engine (CLAUDE.md section 10).

Eligibility is decided here, in plain code, never by a model. A rule is a list of conditions over a few facts about
the learner. The result is one of three words:

    eligible          every condition passes
    not_eligible      at least one condition definitely fails (the failed ones are named)
    check_with_office anything we cannot be sure about: a needed fact is missing, a rule value is still a
                      TODO_VERIFY placeholder, the rule is past its end date, or the record is too old

The engine never guesses. "Awaiting verification" is only a label: a rule that no human has verified still returns
its real status, and the UI shows the label next to it.
"""
from __future__ import annotations

import operator
from datetime import date
from typing import Any

PLACEHOLDER = "TODO_VERIFY"

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
CHECK = "check_with_office"

_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "in": lambda fact, value: fact in value,
    "not_in": lambda fact, value: fact not in value,
}


def is_placeholder(value: Any) -> bool:
    """True for a value nobody has found in an official source yet, such as "TODO_VERIFY" or "TODO_VERIFY: income cap"."""
    if isinstance(value, str):
        return value.strip().upper().startswith(PLACEHOLDER)
    if isinstance(value, (list, tuple)):
        return any(is_placeholder(v) for v in value)
    return False


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _compare(op: str, fact: Any, value: Any) -> bool | None:
    """True or False, or None when the two cannot be compared (a wrong type counts as "not sure", never a guess)."""
    fn = _OPS.get(op)
    if fn is None:
        return None
    try:
        return bool(fn(fact, value))
    except TypeError:
        return None


def _condition_ref(index: int, cond: dict[str, Any]) -> dict[str, Any]:
    return {"index": index, "fact": cond["fact"], "label": cond.get("label_i18n", {})}


def freshness(rule: dict[str, Any], today: date, verified_max_days: int) -> dict[str, Any]:
    """Whether the record can still be relied on. Open-ended rules have `valid_until` null."""
    valid_until_raw = rule.get("valid_until")
    unresolved_end = is_placeholder(valid_until_raw)
    valid_until = None if unresolved_end else parse_date(valid_until_raw)
    expired = valid_until is not None and today > valid_until

    verified_on = parse_date(rule.get("verified_on"))
    basis = verified_on or parse_date(rule.get("entered_on"))
    stale = basis is None or (today - basis).days > verified_max_days
    return {
        "expired": expired,
        "stale": stale,
        "end_date_unknown": unresolved_end,
        "verified_on": verified_on.isoformat() if verified_on else None,
    }


def evaluate(rule: dict[str, Any], facts: dict[str, Any], today: date, verified_max_days: int = 90) -> dict[str, Any]:
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for index, cond in enumerate(rule.get("conditions", [])):
        ref = _condition_ref(index, cond)
        if is_placeholder(cond.get("value")):
            unresolved.append(ref)
            continue
        fact = facts.get(cond["fact"])
        if fact is None:
            missing.append(ref)
            continue
        outcome = _compare(cond["op"], fact, cond["value"])
        if outcome is None:
            unresolved.append(ref)
        elif outcome:
            passed.append(ref)
        else:
            failed.append(ref)

    fresh = freshness(rule, today, verified_max_days)
    cannot_rely = fresh["expired"] or fresh["stale"] or fresh["end_date_unknown"]

    if cannot_rely:
        status = CHECK
    elif failed:
        status = NOT_ELIGIBLE
    elif missing or unresolved:
        status = CHECK
    else:
        status = ELIGIBLE

    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "missing": missing,
        "unresolved": unresolved,
        "docs_to_prepare": list(rule.get("docs_required", [])),
        "source": {"title": rule.get("source_title"), "url": rule.get("source_url"), "entered_on": rule.get("entered_on")},
        "verified_on": fresh["verified_on"],
        "awaiting_verification": fresh["verified_on"] is None,
        "stale": fresh["stale"],
        "expired": fresh["expired"],
    }
