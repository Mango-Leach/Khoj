"""Machine-translates each scheme's name, summary, note and condition labels into Hindi and Marathi with Gemini.

Writes backend/data/schemes_i18n.json. The app shows these lines with a "machine-translated" label until a Hindi and a
Marathi speaker have reviewed them. The rules themselves (values, operators, sources) are never sent or changed:
only the plain-language text. Scheme text has no learner data, so sending it to Gemini is fine.

    python scripts/translate_schemes.py [--only scheme_id] [--force]

Existing entries are kept unless --force is given. Uses GEMINI_API_KEY from the repo-root .env.
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

OUT = ROOT / "backend" / "data" / "schemes_i18n.json"
VERSION = "scheme-translate-v1"
NOTE = "MACHINE-TRANSLATED by scripts/translate_schemes.py (Gemini). Not yet reviewed by a Hindi or Marathi speaker; the app labels it as such."
SYSTEM = (
    "You translate short government-scheme descriptions for rural teenagers in Maharashtra. Translate into simple, everyday "
    "Hindi and simple, everyday Marathi (Devanagari). Keep the meaning exactly. Do not add or remove facts. Keep every number, "
    "amount (Rs), age, class and proper name (PM Vishwakarma, NMMSS, NAPS, NATS, MahaDBT, Aadhaar) as given. 'Rs 2.5 lakh' "
    "becomes '2.5 लाख रुपये'. Output JSON only: "
    '{"hi": {"name": "", "summary": "", "note": "", "conditions": [""]}, "mr": {"name": "", "summary": "", "note": "", "conditions": [""]}} '
    "with one entry in conditions for each condition, in the same order. If the note is empty, return an empty string."
)


class Block(BaseModel):
    name: str = ""
    summary: str = ""
    note: str = ""
    conditions: list[str] = []


class Translated(BaseModel):
    hi: Block = Block()
    mr: Block = Block()


async def translate(llm: LLMService, scheme: dict) -> dict | None:
    conds = [c["label_i18n"]["en"] for c in scheme["conditions"]]
    prompt = (
        f"NAME: {scheme['name_i18n']['en']}\nSUMMARY: {scheme['summary_i18n']['en']}\n"
        f"NOTE: {(scheme.get('note_i18n') or {}).get('en', '')}\nCONDITIONS:\n" + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(conds))
    )
    req = LLMRequest(
        task=Task.INGESTION,  # routed to Gemini; no learner data is involved
        system=SYSTEM,
        prompt=prompt,
        schema=Translated.model_json_schema(),
        temperature=0.0,
        prompt_version=VERSION,
    )
    result = await llm.generate(req, Translated, fallback=lambda: Translated())
    if result.source == "fallback":
        return None
    out = {}
    for lang in ("hi", "mr"):
        block: Block = getattr(result.value, lang)
        if not block.name or not block.summary or len(block.conditions) != len(conds) or not all(block.conditions):
            return None
        out[lang] = block.model_dump()
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    settings = get_settings().model_copy(update={"llm_mode": "live", "llm_route_ingestion": "gemini"})
    llm = LLMService(settings, build_providers(settings), MemoryCache())
    existing = json.loads(OUT.read_text(encoding="utf-8")).get("schemes", {}) if OUT.exists() else {}
    todo = [s for s in catalog.schemes() if (not args.only or s["id"] == args.only) and (args.force or s["id"] not in existing)]
    print(f"{len(todo)} scheme(s) to translate")

    failed = []
    for scheme in todo:
        out = await translate(llm, scheme)
        if out is None:
            failed.append(scheme["id"])
            print("  FAILED", scheme["id"])
            continue
        existing[scheme["id"]] = out
        OUT.write_text(json.dumps({"_note": NOTE, "schemes": existing}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("  ok    ", scheme["id"])
    print(f"done. {len(existing)} translated, {len(failed)} failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
