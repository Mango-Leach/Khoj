"""Checks what each Gnani key can do: text to speech, speech to text, and the Evon text model.

For every configured key (GNANI_API_KEY_ID, GNANI_API_KEY_ID_2) it makes the smallest real call of each
kind and prints the HTTP status and Gnani's error code. It never prints a key. Speech to text is tested
on the audio that text to speech just produced, so no recording is needed (this proves the plumbing, not
accuracy on real voices).

    python scripts/probe_gnani.py [--save-dir DIR]     # DIR keeps the generated clips (for the browser test)

Spends a few credits per key.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.stdout.reconfigure(encoding="utf-8")
from app.config import get_settings  # noqa: E402
from app.services.gnani import LANG_CODE, error_code  # noqa: E402

SENTENCES = {
    "hi": "मुझे सिलाई करना पसंद है और मैं घर पर कपड़े सिलती हूँ।",
    "mr": "मला शिवणकाम करायला आवडतं आणि मी घरी कपडे शिवते.",
    "en": "I like stitching clothes and I repair sewing machines at home.",
}


def describe(resp: httpx.Response) -> str:
    if resp.status_code == 200:
        return "ok"
    return f"HTTP {resp.status_code} {error_code(resp) or resp.text[:80].replace(chr(10), ' ')}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-dir", default=None)
    args = ap.parse_args()
    s = get_settings()
    keys = [k for k in (s.gnani_api_key_id, s.gnani_api_key_id_2) if k.strip()]
    print(f"{len(keys)} key(s) configured; TTS model {s.gnani_tts_model}, voice {s.gnani_tts_voice}, STT model {s.gnani_stt_model or 'default'}")
    base = s.gnani_base_url.rstrip("/")
    if args.save_dir:
        Path(args.save_dir).mkdir(parents=True, exist_ok=True)

    for n, key in enumerate(keys, 1):
        print(f"\n=== key {n} ===")
        headers = {"X-API-Key-ID": key}
        with httpx.Client(timeout=60) as client:
            clips: dict[str, bytes] = {}
            for lang, text in SENTENCES.items():
                t = time.perf_counter()
                body = {"text": text, "model": s.gnani_tts_model, "voice": s.gnani_tts_voice, "language": LANG_CODE[lang],
                        "audio_config": {"container": "mp3", "bitrate": "64k", "sample_rate": 24000}}
                r = client.post(f"{base}/api/v1/tts/inference", headers={**headers, "Content-Type": "application/json"}, json=body)
                dt = time.perf_counter() - t
                note = f"{len(r.content)} bytes, {r.headers.get('content-type', '?')}" if r.status_code == 200 else ""
                print(f"  TTS {lang}: {describe(r)} {note} ({dt:.1f}s)")
                if r.status_code == 200:
                    clips[lang] = r.content
                    if args.save_dir and n == 1:
                        (Path(args.save_dir) / f"tts_{lang}.mp3").write_bytes(r.content)
            for lang, audio in clips.items():
                t = time.perf_counter()
                data = {"language_code": LANG_CODE[lang]}
                if s.gnani_stt_model:
                    data["model"] = s.gnani_stt_model
                r = client.post(f"{base}/stt/v3", headers=headers, data=data, files={"audio_file": (f"{lang}.mp3", audio, "audio/mpeg")})
                dt = time.perf_counter() - t
                heard = r.json().get("transcript", "") if r.status_code == 200 else ""
                print(f"  STT {lang}: {describe(r)} ({dt:.1f}s)")
                if heard:
                    print(f"      said : {SENTENCES[lang]}")
                    print(f"      heard: {heard}")
            t = time.perf_counter()
            r = client.post(f"{base}/v1/chat/completions", headers=headers, json={
                "model": "evon-v3.5", "temperature": 0, "max_tokens": 200,
                "messages": [{"role": "user", "content": "Translate to simple English and answer only with the translation: मला शिवणकाम करायला आवडतं"}]})
            dt = time.perf_counter() - t
            print(f"  LLM evon: {describe(r)} ({dt:.1f}s)")
            if r.status_code == 200:
                try:
                    msg = r.json()["choices"][0]["message"]
                    print(f"      reply: {str(msg.get('content'))[:120]!r}")
                except (KeyError, IndexError, ValueError):
                    print("      (reply not in the expected shape)")


if __name__ == "__main__":
    main()
