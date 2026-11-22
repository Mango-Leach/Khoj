"""Gnani Vachana client: speech to text and text to speech, over a pool of API keys.

The first key is used until Gnani says it is out of credit or quota; then the next one. A key that
reports "no credit" is left alone for a cool-down, a daily quota until midnight IST, an invalid key
for the rest of the process. Keys are never logged, returned or put in an error message.

Facts from docs.gnani.ai (checked 2026-11):
  auth          header X-API-Key-ID: <key>
  STT           POST {base}/stt/v3, multipart: audio_file (wav, mp3, ogg, flac, aac, m4a; at most 30 s),
                language_code (hi-IN, mr-IN, en-IN), optional model. Answer: {"transcript": "..."}
  TTS           POST {base}/api/v1/tts/inference, JSON: text, model, voice, language, audio_config.
                Answer: the audio bytes themselves.
  402           insufficient credit
  429           RATE_LIMITED (an example says only one active request per key) or a daily token quota
  401 / 403     invalid key / key without access to that service
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

import httpx

from app.config import Settings

log = logging.getLogger("khoj.gnani")

Service = Literal["stt", "tts"]
LANG_CODE = {"en": "en-IN", "hi": "hi-IN", "mr": "mr-IN"}
IST = timezone(timedelta(hours=5, minutes=30))

# Why a call could not be completed. The router turns these into API errors.
NOT_CONFIGURED = "not_configured"  # no key set
EXHAUSTED = "exhausted"  # every key is out of credit, quota or access
RATE_LIMITED = "rate_limited"  # every key said "slow down"
UNAVAILABLE = "unavailable"  # Gnani errored or timed out
BAD_AUDIO = "bad_audio"  # the clip itself was refused (too long, unreadable, empty)


class GnaniError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def seconds_until_midnight_ist(now: datetime | None = None) -> float:
    now = (now or datetime.now(timezone.utc)).astimezone(IST)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (midnight - now).total_seconds())


def error_code(resp: httpx.Response) -> str:
    """The machine code in a Gnani error body. Gnani uses several body shapes."""
    try:
        body = resp.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("error_code") or detail.get("code") or "")
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("code") or err.get("type") or "")
    if isinstance(err, str):
        return str(body.get("code") or err)
    return str(body.get("code") or "")


@dataclass
class KeyPool:
    """Ordered keys with a note of which ones to skip, per service, and until when."""

    keys: list[str]
    clock: Callable[[], float] = time.monotonic
    _skip: dict[tuple[int, Service], float] = field(default_factory=dict)
    _locks: dict[int, asyncio.Lock] = field(default_factory=dict)

    def usable(self, service: Service) -> list[int]:
        now = self.clock()
        return [i for i in range(len(self.keys)) if self._skip.get((i, service), 0.0) <= now]

    def skip(self, index: int, service: Service, seconds: float | None) -> None:
        """Leave a key alone for `seconds`; None means for the rest of this process."""
        self._skip[(index, service)] = float("inf") if seconds is None else self.clock() + seconds

    def lock(self, index: int) -> asyncio.Lock:
        # One request at a time per key: Gnani's own example error is "Only 1 active request is allowed at a time".
        return self._locks.setdefault(index, asyncio.Lock())

    def status(self) -> dict[str, Any]:
        return {
            "keys_configured": len(self.keys),
            "stt_keys_usable": len(self.usable("stt")),
            "tts_keys_usable": len(self.usable("tts")),
        }


class GnaniClient:
    def __init__(self, settings: Settings, pool: KeyPool | None = None) -> None:
        self.settings = settings
        keys = [k.strip() for k in (settings.gnani_api_key_id, settings.gnani_api_key_id_2) if k and k.strip()]
        self.pool = pool or KeyPool(keys)
        self.base = settings.gnani_base_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.pool.keys)

    # -- the shared call: try each usable key in turn --------------------------------

    async def _send(self, service: Service, send: Callable[[httpx.AsyncClient, dict[str, str]], Any]) -> httpx.Response:
        if not self.configured:
            raise GnaniError(NOT_CONFIGURED)
        saw_rate_limit = saw_trouble = False
        for round_ in (1, 2):  # a second pass after a short pause covers a momentary rate limit or hiccup
            if round_ == 2:
                if not (saw_rate_limit or saw_trouble):
                    break
                await asyncio.sleep(1.0)
                saw_rate_limit = saw_trouble = False
            usable = self.pool.usable(service)
            if not usable:
                raise GnaniError(EXHAUSTED)
            for index in usable:
                async with self.pool.lock(index):
                    try:
                        async with httpx.AsyncClient(timeout=self.settings.gnani_timeout_s) as client:
                            resp = await send(client, {"X-API-Key-ID": self.pool.keys[index]})
                    except httpx.HTTPError as exc:
                        log.warning("gnani call failed", extra={"service": service, "key": index + 1, "error": type(exc).__name__})
                        saw_trouble = True
                        continue
                verdict = self._judge(service, index, resp)
                if verdict == "ok":
                    return resp
                if verdict == "bad_request":
                    raise GnaniError(BAD_AUDIO, error_code(resp))
                saw_rate_limit |= verdict == "rate_limited"
                saw_trouble |= verdict == "trouble"
        if saw_rate_limit:
            raise GnaniError(RATE_LIMITED)
        if not self.pool.usable(service):
            raise GnaniError(EXHAUSTED)
        raise GnaniError(UNAVAILABLE)

    def _judge(self, service: Service, index: int, resp: httpx.Response) -> str:
        """Returns ok | next (try another key) | rate_limited | trouble | bad_request, and records which keys to skip."""
        status = resp.status_code
        if status == 200:
            return "ok"
        code = error_code(resp).upper()
        label = {"service": service, "key": index + 1, "status": status, "code": code}
        if status == 402:  # insufficient credit
            log.warning("gnani key out of credit", extra=label)
            self.pool.skip(index, service, self.settings.gnani_key_cooldown_s)
            return "next"
        if status == 429 and "QUOTA" in code:
            log.warning("gnani key out of daily quota", extra=label)
            self.pool.skip(index, service, seconds_until_midnight_ist())
            return "next"
        if status == 429:
            return "rate_limited"
        if status in (401, 403):
            log.warning("gnani key refused", extra=label)
            self.pool.skip(index, service, None)  # invalid, or no access to this service
            return "next"
        if status in (408, 500, 502, 503, 504):
            log.warning("gnani trouble", extra=label)
            return "trouble"
        log.warning("gnani rejected the request", extra=label)
        return "bad_request"

    # -- speech to text -------------------------------------------------------------

    async def transcribe(self, audio: bytes, language: str, filename: str = "answer.wav", content_type: str = "audio/wav") -> str:
        data = {"language_code": LANG_CODE[language]}
        if self.settings.gnani_stt_model:
            data["model"] = self.settings.gnani_stt_model

        async def send(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
            return await client.post(f"{self.base}/stt/v3", headers=headers, data=data, files={"audio_file": (filename, audio, content_type)})

        resp = await self._send("stt", send)
        try:
            return str(resp.json().get("transcript") or "").strip()
        except (ValueError, AttributeError) as exc:
            raise GnaniError(UNAVAILABLE, "unreadable answer") from exc

    # -- text to speech -------------------------------------------------------------

    async def synthesize(self, text: str, language: str) -> tuple[bytes, str]:
        body = {
            "text": text,
            "model": self.settings.gnani_tts_model,
            "voice": self.settings.gnani_tts_voice,
            "language": LANG_CODE[language],
            "audio_config": {"container": "mp3", "bitrate": "64k", "sample_rate": 24000},
        }

        async def send(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
            return await client.post(f"{self.base}/api/v1/tts/inference", headers={**headers, "Content-Type": "application/json"}, json=body)

        resp = await self._send("tts", send)
        if not resp.content:
            raise GnaniError(UNAVAILABLE, "empty audio")
        return resp.content, resp.headers.get("content-type", "audio/mpeg")
