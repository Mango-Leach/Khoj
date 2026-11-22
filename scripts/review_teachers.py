"""Review teachers' evidence from the terminal (the same step as POST /admin/teachers/{id}/verify).

    python scripts/review_teachers.py list              (proof waiting for a person, for example when the AI review was unavailable)
    python scripts/review_teachers.py audit [n]         (the last n AI proof reviews, for a spot-check; default 10)
    python scripts/review_teachers.py approve <teacher_id> [note]
    python scripts/review_teachers.py reject <teacher_id> [note]

Proof photos are normally read by the AI review (see services/proof_review.py). A teacher it approves holds 3 learners; `approve`
on that teacher confirms them and lifts the limit to 5, and `reject` overturns it. Every decision made here is written to
`audit_logs` as actor "cli".
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app import db as db_module  # noqa: E402
from app.errors import ApiError  # noqa: E402
from app.services import teacher_assessment  # noqa: E402


async def main(argv: list[str]) -> int:
    database = db_module.get_database()
    if database is None:
        print("MONGODB_URI is not set.")
        return 1
    if not argv or argv[0] not in {"list", "audit", "approve", "reject"}:
        print(__doc__)
        return 2
    if argv[0] == "audit":
        n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 10
        async for r in database["proof_reviews"].find().sort("at", -1).limit(n):
            t = await database["teacher_profiles"].find_one({"_id": r["teacher_id"]}, {"name": 1})
            d = r["decision"]
            print(f"\n{r['at']:%Y-%m-%d %H:%M}  {r['teacher_id']}  {(t or {}).get('name', '?')}  ->  {'APPROVED' if d['approved'] else 'returned'}  areas={d['areas']}  reasons={d['reasons']}")
            for x in r["readings"]:
                v = x["verdict"]
                print(f"  photo {x['photo_id'][:8]}  {x['reading']['doc_type']:<17} good={v['good']}  {x['reading'].get('note', '')[:90]}  [{x['provider']}]")
        return 0
    if argv[0] == "list":
        waiting = await teacher_assessment.pending_review(database)
        if not waiting:
            print("Nobody is waiting for review.")
        for t in waiting:
            print(f"\n{t['teacher_id']}  {t['name']}  ({', '.join(t['roles'])})  {t['block']}, {t['district']}")
            print(f"  skill checks passed: {', '.join(t['passed_areas']) or 'none yet'}")
            for c in t["credentials"]:
                print(f"  - [{c['kind']}] {c['title']}" + (f": {c['note']}" if c["note"] else ""))
        return 0
    if len(argv) < 2:
        print("Give the teacher id.")
        return 2
    try:
        out = await teacher_assessment.review_evidence(database, {"_id": "cli"}, argv[1], "approve" if argv[0] == "approve" else "reject", " ".join(argv[2:])[:300])
    except ApiError as exc:
        print(f"{exc.code}: {exc.message}")
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    code = asyncio.run(main(sys.argv[1:]))
    db_module.close_client()
    raise SystemExit(code)
