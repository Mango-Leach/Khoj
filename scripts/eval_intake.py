"""Scores skill extraction on labelled examples: precision, recall and wrong extras, per language.

For each example (two answers in Hindi or Marathi) it runs the real pipeline pieces:
translate to English with Gemini, then extract skills with each method, with and without the
evidence rule (app/services/evidence.py):

    keywords      the rule-based fallback alone
    ollama        the local model, proposals only
    ollama+rule   the local model, then the evidence rule (what the app ships)
    gemini        the hosted model, proposals only
    gemini+rule   the hosted model, then the evidence rule

A wrong EXTRA skill counts against precision. That is the failure that matters most here: a learner
told they have a skill they never mentioned. The examples are invented (data/eval/intake_labelled.json),
so the numbers describe those sentences only, not real learners. Report them as such.

    python scripts/eval_intake.py [--limit N] [--lang hi|mr] [--ollama-model M] [--gemini-model M]

Uses the keys and hosts in the repo-root .env. Sends only invented sentences, never learner data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import Settings, get_settings  # noqa: E402
from app.models.intake import LLMExtraction  # noqa: E402
from app.services import intake  # noqa: E402
from app.services.cache import MemoryCache  # noqa: E402
from app.services.llm import LLMRequest, LLMService, Task, build_providers  # noqa: E402

DATA = ROOT / "backend" / "data" / "eval" / "intake_labelled.json"
METHODS = ["keywords", "ollama", "ollama+rule", "gemini", "gemini+rule"]


def answers_for(ex: dict, english: tuple[str, str]) -> list[dict]:
    return [
        {"question_id": "q_enjoy", "transcript_native": ex["enjoy"], "transcript_en": english[0]},
        {"question_id": "q_skill", "transcript_native": ex["skill"], "transcript_en": english[1]},
    ]


async def propose(provider, answers: list[dict]) -> tuple[list[str] | None, float]:
    """Skill ids a provider proposes, or None when its output was unusable."""
    doc = {"answers": answers}
    req = LLMRequest(
        task=Task.EXTRACTION,
        system=intake.EXTRACT_SYSTEM,
        prompt=intake._extraction_prompt(doc, "16-18"),
        schema=intake.extraction_schema(),
        temperature=0.0,
        prompt_version=intake.EXTRACT_VERSION,
    )
    t = time.perf_counter()
    try:
        raw = await provider.complete(req)
        skills, _, _, _ = intake.normalise_extraction(LLMExtraction.model_validate_json(raw))
        return skills, time.perf_counter() - t
    except Exception:  # timeouts, bad JSON, provider down: all count as "no usable answer"
        return None, time.perf_counter() - t


def score(rows: list[tuple[set[str], set[str] | None]]) -> dict:
    tp = fp = fn = unusable = exact = clean = 0
    for expected, got in rows:
        if got is None:
            unusable += 1
            got = set()
        tp += len(expected & got)
        fp += len(got - expected)
        fn += len(expected - got)
        exact += got == expected
        clean += not (got - expected)
    n = len(rows)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {"n": n, "precision": precision, "recall": recall, "exact": exact, "no_wrong_extras": clean, "wrong_extras": fp, "missed": fn, "unusable": unusable}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only the first N examples per language")
    ap.add_argument("--lang", choices=["hi", "mr"], default=None)
    ap.add_argument("--ollama-model", default=None)
    ap.add_argument("--gemini-model", default=None)
    args = ap.parse_args()

    base = get_settings()
    s = Settings(
        gemini_api_key=base.gemini_api_key,
        gemini_text_model=args.gemini_model or base.gemini_text_model or "gemini-3.5-flash-lite",
        ollama_text_model=args.ollama_model or base.ollama_text_model or "qwen2.5:3b",
        ollama_host=base.ollama_host,
        llm_mode="live",
        llm_route_translation="gemini",
        ollama_timeout_s=240,
    )
    providers = build_providers(s)
    translator = LLMService(s, providers, MemoryCache())
    print(f"models: ollama={s.ollama_text_model}  gemini={s.gemini_text_model}\n")

    examples = json.loads(DATA.read_text(encoding="utf-8"))["examples"]
    if args.lang:
        examples = [e for e in examples if e["lang"] == args.lang]
    if args.limit:
        seen: dict[str, int] = defaultdict(int)
        kept = []
        for e in examples:
            seen[e["lang"]] += 1
            if seen[e["lang"]] <= args.limit:
                kept.append(e)
        examples = kept

    gate = asyncio.Semaphore(2)  # the free Gemini tier rate-limits bursts

    async def translate(ex: dict) -> tuple[str, str]:
        async with gate:
            a = await intake._to_english(translator, ex["enjoy"], ex["lang"])
            b = await intake._to_english(translator, ex["skill"], ex["lang"])
        return a[0], b[0]

    print(f"translating {len(examples) * 2} answers with Gemini ...")
    english = await asyncio.gather(*(translate(e) for e in examples))

    results: dict[str, dict[str, list[tuple[set[str], set[str] | None]]]] = {m: defaultdict(list) for m in METHODS}
    timings: dict[str, list[float]] = defaultdict(list)
    detail: list[str] = []

    async def hosted() -> dict[int, list[str] | None]:
        async def one(i: int, ex: dict):
            async with gate:
                return i, await propose(providers["gemini"], answers_for(ex, english[i]))

        return {i: r for i, r in await asyncio.gather(*(one(i, e) for i, e in enumerate(examples)))}

    async def local() -> dict[int, list[str] | None]:
        out = {}
        for i, ex in enumerate(examples):  # one at a time: the local model runs on this laptop's CPU
            out[i] = await propose(providers["ollama"], answers_for(ex, english[i]))
        return out

    print("running the local and hosted models (the local one is slow; a few minutes) ...")
    gem, loc = await asyncio.gather(hosted(), local())

    for i, ex in enumerate(examples):
        answers = answers_for(ex, english[i])
        expected = set(ex["expected"])
        lang = ex["lang"]
        kw = set(intake.normalise_extraction(intake.keyword_extraction(answers))[0])
        results["keywords"][lang].append((expected, kw))
        line = [f"[{lang}] {ex['skill'][:46]:46} | EN: {english[i][1][:50]}", f"      expected {sorted(expected)}  keywords {sorted(kw)}"]
        for name, store in (("ollama", loc), ("gemini", gem)):
            proposed, secs = store[i]
            timings[name].append(secs)
            results[name][lang].append((expected, None if proposed is None else set(proposed)))
            gated = None if proposed is None else set(intake.supported_skills(proposed, answers)[0])
            results[f"{name}+rule"][lang].append((expected, gated))
            line.append(f"      {name:7} proposed {proposed}  after rule {sorted(gated) if gated is not None else None}")
        detail.append("\n".join(line))

    print("\n" + "\n".join(detail))
    print("\n=== summary (invented sentences; wrong extras = skills the learner did not say) ===")
    print(f"{'method':14}{'lang':5}{'n':>3}{'precision':>11}{'recall':>8}{'wrong extras':>14}{'examples with none':>20}{'missed':>8}{'unusable':>10}")
    for m in METHODS:
        for lang in ("hi", "mr", "all"):
            rows = [r for k, v in results[m].items() for r in v] if lang == "all" else results[m].get(lang, [])
            if not rows:
                continue
            r = score(rows)
            print(f"{m:14}{lang:5}{r['n']:>3}{r['precision']:>11.2f}{r['recall']:>8.2f}{r['wrong_extras']:>14}{r['no_wrong_extras']:>14}/{r['n']:<5}{r['missed']:>8}{r['unusable']:>10}")
    for name in ("ollama", "gemini"):
        t = sorted(timings[name])
        if t:
            print(f"{name} extraction time: median {t[len(t) // 2]:.1f}s, slowest {t[-1]:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
