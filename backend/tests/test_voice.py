"""The voice endpoints: sign-in needed, size and language checks, no audio kept, caching, and error mapping."""
from __future__ import annotations

import pytest

from app.deps import get_gnani
from app.main import app
from app.routers import voice
from app.services import gnani as gn

from tests.conftest import bearer, sign_in

API = "/api/v1"

AUDIO = b"RIFF" + b"\x00" * 4000


class FakeClient:
    """Stands in for GnaniClient: records what it was asked and can be told to fail."""

    def __init__(self) -> None:
        self.heard: list[tuple[int, str]] = []
        self.spoken: list[tuple[str, str]] = []
        self.fail: gn.GnaniError | None = None
        self.transcript = "मुझे सिलाई पसंद है"
        self.stt_usable = 2
        self.tts_usable = 2

    async def transcribe(self, audio: bytes, language: str, filename: str = "", content_type: str = "") -> str:
        if self.fail:
            raise self.fail
        self.heard.append((len(audio), language))
        return self.transcript

    async def synthesize(self, text: str, language: str):
        if self.fail:
            raise self.fail
        self.spoken.append((text, language))
        return b"ID3-" + text.encode()[:20], "audio/mpeg"


class Pool:
    def __init__(self, fake: FakeClient) -> None:
        self.fake = fake

    def status(self):
        return {"keys_configured": 2, "stt_keys_usable": self.fake.stt_usable, "tts_keys_usable": self.fake.tts_usable}


@pytest.fixture
def fake(client):
    f = FakeClient()
    f.pool = Pool(f)  # type: ignore[assignment]
    app.dependency_overrides[get_gnani] = lambda: f
    voice._recent.clear()
    return f


async def signed_in(client, clock, phone="9876543210"):
    return await sign_in(client, clock, phone)


def asr(client, tokens, audio=AUDIO, language="hi"):
    return client.post(f"{API}/voice/asr", files={"audio": ("answer.wav", audio, "audio/wav")}, data={"language": language}, headers=bearer(tokens))


async def test_voice_needs_a_signed_in_user(client, fake):
    r = await client.post(f"{API}/voice/asr", files={"audio": ("a.wav", AUDIO, "audio/wav")}, data={"language": "hi"})
    assert r.status_code == 401
    assert (await client.post(f"{API}/voice/tts", json={"text": "hello", "language": "en"})).status_code == 401
    assert (await client.get(f"{API}/voice/status")).status_code == 401


async def test_status_tells_the_app_whether_server_speech_can_be_used(client, clock, fake):
    t = await signed_in(client, clock)
    assert (await client.get(f"{API}/voice/status", headers=bearer(t))).json() == {"asr": True, "tts": True}
    fake.stt_usable = 0
    assert (await client.get(f"{API}/voice/status", headers=bearer(t))).json() == {"asr": False, "tts": True}


async def test_a_recording_becomes_a_transcript(client, clock, fake):
    t = await signed_in(client, clock)
    r = await asr(client, t, language="hi")
    assert r.status_code == 200 and r.json() == {"transcript": "मुझे सिलाई पसंद है", "language": "hi"}
    assert fake.heard == [(len(AUDIO), "hi")]


async def test_phone_numbers_are_removed_from_the_transcript(client, clock, fake):
    fake.transcript = "मेरा नंबर 98765 43210 है और मैं सिलाई करती हूँ"
    t = await signed_in(client, clock)
    text = (await asr(client, t)).json()["transcript"]
    assert "98765" not in text and "सिलाई" in text


async def test_the_recording_is_not_kept(client, clock, fake, db):
    t = await signed_in(client, clock)
    before = set(await db.list_collection_names())
    await asr(client, t)
    assert set(await db.list_collection_names()) == before  # nothing new was written anywhere


async def test_bad_recordings_and_languages_are_refused(client, clock, fake):
    t = await signed_in(client, clock)
    assert (await asr(client, t, audio=b"tiny")).json()["code"] == "bad_audio"
    big = await asr(client, t, audio=b"\x00" * (voice.MAX_AUDIO_BYTES + 10))
    assert big.status_code == 413 and big.json()["code"] == "audio_too_large"
    assert (await asr(client, t, language="fr")).status_code == 422
    assert fake.heard == []  # none of them reached Gnani


@pytest.mark.parametrize(
    "reason, status, code",
    [
        (gn.EXHAUSTED, 503, "speech_unavailable"),
        (gn.NOT_CONFIGURED, 503, "speech_unavailable"),
        (gn.UNAVAILABLE, 503, "speech_unavailable"),
        (gn.RATE_LIMITED, 503, "speech_busy"),
        (gn.BAD_AUDIO, 422, "bad_audio"),
    ],
)
async def test_gnani_failures_become_plain_errors_the_app_can_fall_back_from(client, clock, fake, reason, status, code):
    fake.fail = gn.GnaniError(reason)
    t = await signed_in(client, clock)
    r = await asr(client, t)
    assert r.status_code == status and r.json()["code"] == code
    assert "key" not in r.text.lower() or "keys" not in r.text.lower()


async def test_one_person_cannot_burn_the_credits(client, clock, fake, monkeypatch):
    monkeypatch.setitem(voice.LIMITS, "asr", 3)
    t = await signed_in(client, clock)
    for _ in range(3):
        assert (await asr(client, t)).status_code == 200
    r = await asr(client, t)
    assert r.status_code == 429 and r.json()["code"] == "too_many_requests"


async def test_spoken_audio_is_made_once_then_served_from_the_cache(client, clock, fake):
    t = await signed_in(client, clock)
    body = {"text": "आपको क्या करना पसंद है?", "language": "hi"}
    first = await client.post(f"{API}/voice/tts", json=body, headers=bearer(t))
    assert first.status_code == 200 and first.headers["content-type"] == "audio/mpeg" and first.headers["x-khoj-cache"] == "miss"
    second = await client.post(f"{API}/voice/tts", json=body, headers=bearer(t))
    assert second.headers["x-khoj-cache"] == "hit" and second.content == first.content
    assert len(fake.spoken) == 1  # the second one cost no credits
    other_language = await client.post(f"{API}/voice/tts", json={**body, "language": "mr"}, headers=bearer(t))
    assert other_language.headers["x-khoj-cache"] == "miss" and len(fake.spoken) == 2


async def test_a_phone_number_is_never_sent_out_to_be_spoken(client, clock, fake):
    t = await signed_in(client, clock)
    await client.post(f"{API}/voice/tts", json={"text": "call 98765 43210 now", "language": "en"}, headers=bearer(t))
    assert "98765" not in fake.spoken[0][0]


async def test_tts_validates_its_input(client, clock, fake):
    t = await signed_in(client, clock)
    assert (await client.post(f"{API}/voice/tts", json={"text": "", "language": "en"}, headers=bearer(t))).status_code == 422
    assert (await client.post(f"{API}/voice/tts", json={"text": "x" * 600, "language": "en"}, headers=bearer(t))).status_code == 422
    assert (await client.post(f"{API}/voice/tts", json={"text": "hi", "language": "xx"}, headers=bearer(t))).status_code == 422


async def test_health_reports_key_counts_but_never_a_key(client):
    r = await client.get(f"{API}/health")
    speech = r.json()["speech"]
    assert speech["provider"] == "gnani" and {"keys_configured", "stt_keys_usable", "tts_keys_usable"} <= set(speech)
