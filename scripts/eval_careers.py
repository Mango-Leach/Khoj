"""Sanity check of career ranking on the labelled intake sentences. Offline, no model, no network.

For each labelled example it ranks careers from the EXPECTED skills (data/eval/intake_labelled.json) and prints the
top 3. It reports two things:

    coverage   examples whose top career uses a matched or closely related skill
    unmatched  examples where no career matched, so the learner would see only interest-based or starter paths

This does NOT measure "top-3 agreement with a human". That needs a person to label the right careers for each
example, which has not been done. The sentences are invented, so treat the output as a smoke test of the data.

    python scripts/eval_careers.py [--verbose]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.services import catalog  # noqa: E402
from app.services.career_engine import Profile, rank  # noqa: E402

DATA = ROOT / "backend" / "data" / "eval" / "intake_labelled.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    examples = raw["examples"] if isinstance(raw, dict) else raw

    covered, unmatched, no_skills = 0, [], 0
    used: set[str] = set()
    for i, ex in enumerate(examples, 1):
        skills = set(ex["expected"])
        if not skills:
            no_skills += 1
            continue
        top = rank(Profile(skills=skills, district="pune"))[:3]
        used.update(r.career_id for r in top)
        if top and (top[0].matched or top[0].related):
            covered += 1
        else:
            unmatched.append(i)
        if args.verbose:
            names = ", ".join(f"{r.career_id}{'*' if r.matched else ''}" for r in top)
            print(f"{i:>2} [{ex['lang']}] {sorted(skills)} -> {names}")

    with_skills = len(examples) - no_skills
    print(f"\nexamples: {len(examples)} ({no_skills} with no expected skills, skipped)")
    print(f"coverage: {covered}/{with_skills} have a top career built on a matched or closely related skill")
    print(f"unmatched examples: {unmatched or 'none'}")
    print(f"careers that appear in some top 3: {len(used)}/{len(catalog.careers())}")
    print("never in a top 3:", sorted(set(catalog.career_ids()) - used) or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
