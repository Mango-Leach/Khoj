"""Checks that every learning-resource link still answers (the monthly link check for `link_out` records).

    python scripts/check_resources.py

Prints one line per resource. It only reports; it never edits a file and never sets `verified_on`.
Only a person who opens the page and reads it may set `verified_on` in backend/data/resources.json.

Many course sites (SWAYAM, NPTEL, Skill India) build their pages in the browser, so a 200 here proves the address
exists, not that the course is open for enrolment. Certificate errors are reported as they are, never bypassed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.services import catalog  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; link-check)"}


def check(client: httpx.Client, url: str) -> str:
    try:
        r = client.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
        return f"{r.status_code}" + (f" -> {r.url}" if str(r.url) != url else "")
    except httpx.HTTPError as exc:
        return f"ERROR {type(exc).__name__}"


def main() -> int:
    bad = 0
    seen: dict[str, str] = {}
    with httpx.Client() as client:
        for res in catalog.resources():
            if res["url"] not in seen:
                seen[res["url"]] = check(client, res["url"])
            status = seen[res["url"]]
            ok = status.startswith(("200", "301", "302"))
            bad += not ok
            print(f"{'ok ' if ok else 'BAD'} {res['id']:<42} {status[:90]}")
    print(f"\n{len(catalog.resources())} resources, {bad} not answering")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
