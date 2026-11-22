"""The Gnani client: key order, failover on credit/quota/invalid key, per-service access, and secrecy. No network."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
import pytest

from app.config import Settings
from app.services import gnani as gn

KEY1, KEY2 = "secret-key-one-AAAA", "secret-key-two-BBBB"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    async def instant(_):  # the client pauses a second between rounds; tests do not wait
        return None

    monkeypatch.setattr(gn.asyncio, "sleep", instant)


def make_client(clock, keys=(KEY1, KEY2), **settings) -> gn.GnaniClient:
    s = Settings(_env_file=None, gnani_api_key_id=keys[0] if keys else "", gnani_api_key_id_2=keys[1] if len(keys) > 1 else "", **settings)
    return gn.GnaniClient(s, gn.KeyPool([k for k in keys if k], clock=clock))


def serve(monkeypatch, handler):
    """Every httpx.AsyncClient the code creates answers from `handler` instead of the network."""
    real = httpx.AsyncClient
    monkeypatch.setattr(gn.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def ok_stt(text="नमस्ते"):
    return httpx.Response(200, json={"success": True, "transcript": text})


def credit_gone():
    return httpx.Response(402, json={"detail": {"error_code": "INSUFFICIENT_CREDIT", "message": "no credit", "status_code": 402}})


def by_key(**answers):
    """A handler that answers per API key: by_key(one=..., two=...)."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        who = "one" if request.headers["x-api-key-id"] == KEY1 else "two"
        calls.append(who)
        out = answers[who]
        return out() if callable(out) else out

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


async def test_the_first_key_is_used_and_the_second_is_left_alone(monkeypatch, clock):
    h = by_key(one=lambda: ok_stt("one"), two=lambda: ok_stt("two"))
    serve(monkeypatch, h)
    c = make_client(clock)
    assert await c.transcribe(b"x" * 2000, "hi") == "one"
    assert await c.transcribe(b"x" * 2000, "hi") == "one"
    assert h.calls == ["one", "one"]


async def test_no_credit_moves_to_the_second_key_and_the_first_is_left_alone_for_a_while(monkeypatch, clock):
    h = by_key(one=credit_gone, two=lambda: ok_stt("two"))
    serve(monkeypatch, h)
    c = make_client(clock, gnani_key_cooldown_s=900)
    assert await c.transcribe(b"x", "hi") == "two"
    assert await c.transcribe(b"x", "hi") == "two"
    assert h.calls == ["one", "two", "two"]  # key one was not asked again
    clock.now += 901  # after the cool-down the first key gets another chance (it may have been topped up)
    await c.transcribe(b"x", "hi")
    assert h.calls[-2:] == ["one", "two"]


async def test_a_daily_quota_skips_the_key_until_midnight_ist(monkeypatch, clock):
    quota = lambda: httpx.Response(429, json={"error": {"code": "daily_token_quota_exceeded", "message": "used up"}})  # noqa: E731
    h = by_key(one=quota, two=lambda: ok_stt("two"))
    serve(monkeypatch, h)
    # the real code reads the wall clock for "until midnight IST"; fix it so this test cannot depend on the time of day it runs
    monkeypatch.setattr(gn, "seconds_until_midnight_ist", lambda now=None: 6 * 3600.0)
    c = make_client(clock)
    assert await c.transcribe(b"x", "mr") == "two"
    clock.now += 3600  # an hour on: still skipped
    await c.transcribe(b"x", "mr")
    assert h.calls == ["one", "two", "two"]
    clock.now += 24 * 3600  # past midnight: tried again
    await c.transcribe(b"x", "mr")
    assert h.calls[-2:] == ["one", "two"]


async def test_an_invalid_key_is_dropped_for_good(monkeypatch, clock):
    bad = lambda: httpx.Response(401, json={"detail": {"error_code": "INVALID_API_KEY", "message": "no", "status_code": 401}})  # noqa: E731
    h = by_key(one=bad, two=lambda: ok_stt("two"))
    serve(monkeypatch, h)
    c = make_client(clock)
    await c.transcribe(b"x", "en")
    clock.now += 10 * 24 * 3600
    await c.transcribe(b"x", "en")
    assert h.calls == ["one", "two", "two"]


async def test_a_key_without_access_to_one_service_still_works_for_the_other(monkeypatch, clock):
    scope = httpx.Response(403, json={"detail": {"error_code": "SCOPE_NOT_ALLOWED", "message": "Service 'STT' not in allowed scopes", "status_code": 403}})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stt/v3":
            return scope
        return httpx.Response(200, content=b"ID3audio", headers={"content-type": "audio/mpeg"})

    serve(monkeypatch, handler)
    c = make_client(clock, keys=(KEY1,))
    with pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    assert e.value.reason == gn.EXHAUSTED
    audio, kind = await c.synthesize("नमस्ते", "hi")  # the same key still speaks
    assert audio == b"ID3audio" and kind == "audio/mpeg"


async def test_when_every_key_is_out_the_error_says_so(monkeypatch, clock):
    serve(monkeypatch, by_key(one=credit_gone, two=credit_gone))
    c = make_client(clock)
    with pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    assert e.value.reason == gn.EXHAUSTED
    assert c.pool.status()["stt_keys_usable"] == 0
    with pytest.raises(gn.GnaniError) as e2:  # and it does not hammer Gnani again
        await c.transcribe(b"x", "hi")
    assert e2.value.reason == gn.EXHAUSTED


async def test_a_rate_limit_is_retried_after_a_pause_then_reported(monkeypatch, clock):
    limited = lambda: httpx.Response(429, json={"detail": {"error_code": "RATE_LIMITED", "message": "Only 1 active request is allowed at a time.", "status_code": 429}})  # noqa: E731
    h = by_key(one=limited, two=limited)
    serve(monkeypatch, h)
    c = make_client(clock)
    with pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    assert e.value.reason == gn.RATE_LIMITED
    assert h.calls == ["one", "two", "one", "two"]  # both keys, a pause, both again
    assert c.pool.status()["stt_keys_usable"] == 2  # a rate limit is not a lost key


async def test_a_server_hiccup_is_retried(monkeypatch, clock):
    answers = [httpx.Response(503, json={}), ok_stt("fine")]
    serve(monkeypatch, lambda request: answers.pop(0))
    c = make_client(clock, keys=(KEY1,))
    assert await c.transcribe(b"x", "hi") == "fine"


async def test_a_refused_recording_is_not_retried_and_costs_no_key(monkeypatch, clock):
    h = by_key(one=httpx.Response(400, json={"success": False, "error": {"type": "MAX_AUDIO_DURATION_EXCEEDED", "message": "too long"}}), two=lambda: ok_stt())
    serve(monkeypatch, h)
    c = make_client(clock)
    with pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    assert e.value.reason == gn.BAD_AUDIO and e.value.detail == "MAX_AUDIO_DURATION_EXCEEDED"
    assert h.calls == ["one"] and c.pool.status()["stt_keys_usable"] == 2


async def test_no_key_means_not_configured(clock):
    c = make_client(clock, keys=())
    assert not c.configured
    with pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    assert e.value.reason == gn.NOT_CONFIGURED


async def test_keys_never_appear_in_logs_or_errors(monkeypatch, clock, caplog):
    serve(monkeypatch, by_key(one=credit_gone, two=lambda: httpx.Response(401, json={"detail": {"error_code": "INVALID_API_KEY"}})))
    c = make_client(clock)
    with caplog.at_level(logging.DEBUG), pytest.raises(gn.GnaniError) as e:
        await c.transcribe(b"x", "hi")
    everything = caplog.text + str(e.value) + repr(c.pool.status())
    assert KEY1 not in everything and KEY2 not in everything


async def test_requests_are_shaped_the_way_gnani_documents(monkeypatch, clock):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/stt/v3":
            return ok_stt("ठीक है")
        return httpx.Response(200, content=b"mp3bytes", headers={"content-type": "audio/mpeg"})

    serve(monkeypatch, handler)
    c = make_client(clock, keys=(KEY1,), gnani_stt_model="prisma-v3.0")
    assert await c.transcribe(b"RIFFdata", "mr") == "ठीक है"
    stt = seen[0]
    assert str(stt.url) == "https://api.vachana.ai/stt/v3" and stt.headers["x-api-key-id"] == KEY1
    body = stt.read()
    assert b'name="language_code"' in body and b"mr-IN" in body and b'name="audio_file"' in body and b"prisma-v3.0" in body

    await c.synthesize("नमस्कार", "hi")
    tts = seen[1]
    assert str(tts.url) == "https://api.vachana.ai/api/v1/tts/inference" and tts.headers["x-api-key-id"] == KEY1
    import json

    payload = json.loads(tts.read())
    assert payload["language"] == "hi-IN" and payload["model"] == "timbre-v3.0" and payload["voice"] and payload["audio_config"]["container"] == "mp3"


def test_error_codes_are_read_from_every_body_shape():
    r = lambda body: httpx.Response(400, json=body)  # noqa: E731
    assert gn.error_code(r({"detail": {"error_code": "RATE_LIMITED"}})) == "RATE_LIMITED"
    assert gn.error_code(r({"error": {"code": "daily_token_quota_exceeded"}})) == "daily_token_quota_exceeded"
    assert gn.error_code(r({"success": False, "error": {"type": "EMPTY_AUDIO"}})) == "EMPTY_AUDIO"
    assert gn.error_code(r({"error": "Gateway Timeout", "code": "UPSTREAM_TIMEOUT"})) == "UPSTREAM_TIMEOUT"
    assert gn.error_code(httpx.Response(500, content=b"not json")) == ""


def test_midnight_ist_is_never_less_than_a_minute_away():
    just_before = datetime(2026, 11, 19, 18, 29, 30, tzinfo=timezone.utc)  # 23:59:30 IST
    assert gn.seconds_until_midnight_ist(just_before) == 60.0  # floored
    noon_utc = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)  # 17:30 IST
    assert gn.seconds_until_midnight_ist(noon_utc) == 6.5 * 3600
