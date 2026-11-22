"""Speech for the app: turn a recorded answer into text, and text into spoken audio.

The browser never sees a Gnani key; it sends audio here and this module calls Gnani. A recorded
answer is held in memory only long enough to be sent on, then dropped: it is never written to disk or
the database and never logged (CLAUDE.md: "Do not store raw voice audio").
"""
from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.deps import current_user, get_db, get_gnani
from app.errors import ApiError
from app.services import gnani as gn
from app import timeutil
from app.services.privacy import scrub_text

router = APIRouter(prefix="/voice", tags=["voice"])

Lang = Literal["en", "hi", "mr"]
MAX_AUDIO_BYTES = 2_500_000  # a 30 s clip is under 1 MB as 16 kHz mono WAV
MIN_AUDIO_BYTES = 1_000
MAX_TTS_CHARS = 500
WINDOW_S = 600
LIMITS = {"asr": 40, "tts": 120}  # calls per user per 10 minutes: protects the credits, not a quota

_recent: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _limit(user_id: str, kind: str) -> None:
    now = time.monotonic()
    calls = _recent[(user_id, kind)]
    while calls and now - calls[0] > WINDOW_S:
        calls.popleft()
    if len(calls) >= LIMITS[kind]:
        raise ApiError(429, "too_many_requests", "Too many voice requests.", "Please wait a few minutes.")
    calls.append(now)


def _speech_error(exc: gn.GnaniError) -> ApiError:
    if exc.reason == gn.BAD_AUDIO:
        return ApiError(422, "bad_audio", "We could not use that recording.", "Try again, or type your answer.")
    if exc.reason == gn.RATE_LIMITED:
        return ApiError(503, "speech_busy", "The voice service is busy.", "Try again in a moment, or type.")
    # not configured, out of credit on every key, or Gnani down: the app falls back to browser speech or typing
    return ApiError(503, "speech_unavailable", "Voice is not available right now.", "Type your answer instead.")


@router.get("/status")
async def status(_: dict[str, Any] = Depends(current_user), client: gn.GnaniClient = Depends(get_gnani)) -> dict[str, Any]:
    """Whether server speech can be used right now, so the app can choose between it and the browser."""
    pool = client.pool.status()
    return {"asr": pool["stt_keys_usable"] > 0, "tts": pool["tts_keys_usable"] > 0}


@router.post("/asr")
async def transcribe(
    audio: UploadFile = File(...),
    language: Lang = Form(...),
    user: dict[str, Any] = Depends(current_user),
    client: gn.GnaniClient = Depends(get_gnani),
) -> dict[str, str]:
    _limit(user["_id"], "asr")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError(413, "audio_too_large", "That recording is too long.", "Keep each answer under 30 seconds.")
    if len(data) < MIN_AUDIO_BYTES:
        raise ApiError(422, "bad_audio", "We could not use that recording.", "Try again, or type your answer.")
    try:
        text = await client.transcribe(data, language, filename=audio.filename or "answer.wav", content_type=audio.content_type or "audio/wav")
    except gn.GnaniError as exc:
        raise _speech_error(exc) from exc
    finally:
        del data  # the recording is not kept anywhere
    return {"transcript": scrub_text(text, limit=2000), "language": language}


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    language: Lang = "en"


@router.post("/tts")
async def speak(
    body: SpeakIn,
    user: dict[str, Any] = Depends(current_user),
    client: gn.GnaniClient = Depends(get_gnani),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Spoken audio for a line of text. Repeated lines (the questions, the buttons) come from a cache and cost nothing."""
    text = scrub_text(body.text, limit=MAX_TTS_CHARS)  # a typed answer can hold a phone number; never speak it out to a third party
    if len(text) < 1:
        raise ApiError(422, "empty_answer", "There is nothing to read.", "")
    key = hashlib.sha256(f"{settings.gnani_tts_model}|{settings.gnani_tts_voice}|{body.language}|{text}".encode()).hexdigest()
    cached = await db["tts_cache"].find_one({"_id": key})
    if cached is not None:
        return Response(content=bytes(cached["audio"]), media_type=cached["content_type"], headers={"X-Khoj-Cache": "hit"})
    _limit(user["_id"], "tts")
    try:
        audio, content_type = await client.synthesize(text, body.language)
    except gn.GnaniError as exc:
        raise _speech_error(exc) from exc
    await db["tts_cache"].update_one(
        {"_id": key},
        {"$set": {"audio": audio, "content_type": content_type, "language": body.language, "chars": len(text), "created_at": timeutil.utcnow()}},
        upsert=True,
    )
    return Response(content=audio, media_type=content_type, headers={"X-Khoj-Cache": "miss"})
