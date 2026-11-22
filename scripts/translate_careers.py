"""Machine-translates each career's five-rung ladder (titles and details) into Hindi and Marathi with Gemini.

Writes backend/data/careers_i18n.json. The app shows these lines with a "machine-translated" label until a Hindi and
a Marathi speaker have reviewed them. Names, summaries and first-income steps are already written by hand in
careers.json and are not touched. Career text has no learner data, so sending it to Gemini is fine.

    python scripts/translate_careers.py [--only career_id] [--force]

Existing entries are kept unless --force is given, so a re-run only fills gaps. Uses GEMINI_API_KEY from the repo-root .env.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from pydantic import BaseModel  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services import catalog  # noqa: E402
from app.services.cache import MemoryCache  # noqa: E402
from app.services.llm import LLMRequest, LLMService, Task, build_providers  # noqa: E402

OUT = ROOT / "backend" / "data" / "careers_i18n.json"
VERSION = "career-ladder-translate-v1"
NOTE = "MACHINE-TRANSLATED by scripts/translate_careers.py (Gemini). Not yet reviewed by a Hindi or Marathi speaker; the app labels it as such."
SYSTEM = (
    "You translate short career-guidance text for rural teenagers in Maharashtra. Translate into simple, everyday Hindi "
    "and simple, everyday Marathi (Devanagari). Keep the meaning exactly. Do not add or remove facts, numbers or names. "
    'Output JSON only: {"hi": [{"title": "...", "detail": "..."}], "mr": [{"title": "...", "detail": "..."}]} with one '
    "entry per rung, in the same order."
)


class Rung(BaseModel):
    title: str
    detail: str


class Ladder(BaseModel):
    hi: list[Rung] = []
    mr: list[Rung] = []


async def translate(llm: LLMService, career: dict) -> dict | None:
    lines = [f"{i + 1}. TITLE: {r['title']}\n   DETAIL: {r['detail']}" for i, r in enumerate(career["ladder"])]
    req = LLMRequest(
        task=Task.INGESTION,  # routed to Gemini; no learner data is involved
        system=SYSTEM,
        prompt=f"Career: {career['name']['en']}\nRungs:\n" + "\n".join(lines),
        schema=Ladder.model_json_schema(),
        temperature=0.0,
        prompt_version=VERSION,
    )
    result = await llm.generate(req, Ladder, fallback=lambda: Ladder())
    n = len(career["ladder"])
    if result.source == "fallback" or len(result.value.hi) != n or len(result.value.mr) != n:
        return None
    return {lang: {"ladder": [r.model_dump() for r in getattr(result.value, lang)]} for lang in ("hi", "mr")}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    settings = get_settings().model_copy(update={"llm_mode": "live", "llm_route_ingestion": "gemini"})
    llm = LLMService(settings, build_providers(settings), MemoryCache())
    existing = json.loads(OUT.read_text(encoding="utf-8")).get("careers", {}) if OUT.exists() else {}
    todo = [c for c in catalog.careers() if (not args.only or c["career_id"] == args.only) and (args.force or c["career_id"] not in existing)]
    print(f"{len(todo)} career(s) to translate")

    failed = []
    for career in todo:
        out = await translate(llm, career)
        if out is None:
            failed.append(career["career_id"])
            print("  FAILED", career["career_id"])
            continue
        existing[career["career_id"]] = out
        OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # save as we go
        print("  ok    ", career["career_id"])
    print(f"done. {len(existing)} translated, {len(failed)} failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
