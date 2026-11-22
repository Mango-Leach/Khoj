"""LLM routing, failover, validation retry, cache and cache_only behaviour. No network."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.services.cache import MemoryCache
from app.services.llm import (
    LLMRequest,
    LLMService,
    LLMUnavailable,
    ProviderError,
    Task,
    parse_json_output,
    provider_order,
    route_for,
)
from app.services.vision import analyze_images


class Skills(BaseModel):
    skills: list[str]


def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, llm_mode="live", **overrides)


class FakeProvider:
    def __init__(self, name: str, outputs: list):
        self.name = name
        self.outputs = list(outputs)  # str = model output, Exception = raise
        self.calls = 0

    def model_for(self, req: LLMRequest) -> str:
        return f"{self.name}-model"

    async def complete(self, req: LLMRequest) -> str:
        self.calls += 1
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def service(settings: Settings, ollama: FakeProvider, gemini: FakeProvider, cache=None) -> LLMService:
    return LLMService(settings, {"ollama": ollama, "gemini": gemini}, cache or MemoryCache())


def req(task: Task = Task.EXTRACTION, prompt: str = "I repair sewing machines") -> LLMRequest:
    return LLMRequest(task=task, prompt=prompt)


# --- routing ---------------------------------------------------------------


def test_default_routes_match_the_decided_split():
    s = make_settings()
    assert route_for(s, Task.EXTRACTION) == "ollama"
    assert route_for(s, Task.DRAFTING) == "ollama"
    assert route_for(s, Task.REASONING) == "ollama"
    assert route_for(s, Task.INGESTION) == "gemini"
    assert route_for(s, Task.VISION) == "ollama"


def test_route_can_be_overridden_per_task():
    s = make_settings(llm_route_extraction="gemini")
    assert provider_order(s, Task.EXTRACTION) == ["gemini", "ollama"]


def test_text_tasks_fail_over_to_the_other_provider():
    s = make_settings()
    assert provider_order(s, Task.EXTRACTION) == ["ollama", "gemini"]
    assert provider_order(s, Task.INGESTION) == ["gemini", "ollama"]


def test_student_photos_stay_local_by_default():
    assert provider_order(make_settings(), Task.VISION) == ["ollama"]


def test_photo_fallback_to_gemini_needs_the_flag():
    assert provider_order(make_settings(vision_fallback_to_gemini=True), Task.VISION) == ["ollama", "gemini"]


# --- generation and failover ----------------------------------------------


async def test_uses_primary_provider_when_it_works():
    ollama = FakeProvider("ollama", ['{"skills": ["stitching"]}'])
    gemini = FakeProvider("gemini", [])
    result = await service(make_settings(), ollama, gemini).generate(req(), Skills)
    assert result.value.skills == ["stitching"]
    assert result.source == "ollama"
    assert gemini.calls == 0


async def test_fails_over_when_primary_errors():
    ollama = FakeProvider("ollama", [ProviderError("down")])
    gemini = FakeProvider("gemini", ['{"skills": ["accounts"]}'])
    result = await service(make_settings(), ollama, gemini).generate(req(), Skills)
    assert result.source == "gemini"
    assert result.value.skills == ["accounts"]


async def test_retries_once_on_invalid_json_then_succeeds_on_same_provider():
    ollama = FakeProvider("ollama", ["not json", '{"skills": ["repair"]}'])
    gemini = FakeProvider("gemini", [])
    result = await service(make_settings(), ollama, gemini).generate(req(), Skills)
    assert result.source == "ollama"
    assert ollama.calls == 2
    assert gemini.calls == 0


async def test_invalid_twice_falls_over_to_other_provider():
    ollama = FakeProvider("ollama", ["nope", '{"wrong": 1}'])
    gemini = FakeProvider("gemini", ['{"skills": ["dairy"]}'])
    result = await service(make_settings(), ollama, gemini).generate(req(), Skills)
    assert result.source == "gemini"
    assert ollama.calls == 2


async def test_uses_rule_based_fallback_when_all_providers_fail():
    ollama = FakeProvider("ollama", [ProviderError("down")])
    gemini = FakeProvider("gemini", [ProviderError("no key")])
    result = await service(make_settings(), ollama, gemini).generate(
        req(), Skills, fallback=lambda: Skills(skills=["keyword-match"])
    )
    assert result.source == "fallback"
    assert result.value.skills == ["keyword-match"]


async def test_raises_when_everything_fails_and_no_fallback():
    ollama = FakeProvider("ollama", [ProviderError("down")])
    gemini = FakeProvider("gemini", [ProviderError("down")])
    with pytest.raises(LLMUnavailable):
        await service(make_settings(), ollama, gemini).generate(req(), Skills)


async def test_code_fenced_json_is_accepted():
    assert parse_json_output('```json\n{"skills": ["a"]}\n```', Skills).skills == ["a"]


# --- cache and cache_only --------------------------------------------------


async def test_second_identical_call_is_served_from_cache():
    ollama = FakeProvider("ollama", ['{"skills": ["stitching"]}'])
    gemini = FakeProvider("gemini", [])
    svc = service(make_settings(), ollama, gemini)
    first = await svc.generate(req(), Skills)
    second = await svc.generate(req(), Skills)
    assert first.source == "ollama"
    assert second.source == "cache"
    assert ollama.calls == 1


async def test_cache_hit_survives_a_provider_outage():
    cache = MemoryCache()
    first = service(make_settings(), FakeProvider("ollama", ['{"skills": ["x"]}']), FakeProvider("gemini", []), cache)
    await first.generate(req(), Skills)
    down = service(
        make_settings(),
        FakeProvider("ollama", [ProviderError("down")]),
        FakeProvider("gemini", [ProviderError("down")]),
        cache,
    )
    assert (await down.generate(req(), Skills)).source == "cache"


async def test_different_prompts_do_not_share_cache_entries():
    ollama = FakeProvider("ollama", ['{"skills": ["a"]}', '{"skills": ["b"]}'])
    svc = service(make_settings(), ollama, FakeProvider("gemini", []))
    a = await svc.generate(req(prompt="one"), Skills)
    b = await svc.generate(req(prompt="two"), Skills)
    assert (a.value.skills, b.value.skills) == (["a"], ["b"])
    assert ollama.calls == 2


async def test_cache_only_mode_never_calls_a_provider():
    ollama = FakeProvider("ollama", ['{"skills": ["x"]}'])
    gemini = FakeProvider("gemini", ['{"skills": ["x"]}'])
    svc = service(Settings(_env_file=None, llm_mode="cache_only"), ollama, gemini)
    result = await svc.generate(req(), Skills, fallback=lambda: Skills(skills=["fallback"]))
    assert result.source == "fallback"
    assert ollama.calls == gemini.calls == 0


class BrokenCache:
    async def get(self, key):
        raise RuntimeError("db down")

    async def set(self, key, value):
        raise RuntimeError("db down")


async def test_a_broken_cache_never_breaks_a_request():
    ollama = FakeProvider("ollama", ['{"skills": ["x"]}'])
    result = await service(make_settings(), ollama, FakeProvider("gemini", []), BrokenCache()).generate(req(), Skills)
    assert result.source == "ollama"


# --- vision ----------------------------------------------------------------


async def test_vision_without_flag_never_reaches_gemini():
    ollama = FakeProvider("ollama", [ProviderError("down")])
    gemini = FakeProvider("gemini", ['{"skills": ["leaked"]}'])
    svc = service(make_settings(), ollama, gemini)
    result = await analyze_images(svc, [b"jpeg-bytes"], "check the seam", Skills, fallback=lambda: Skills(skills=["teacher-queue"]))
    assert result.source == "fallback"
    assert gemini.calls == 0


async def test_vision_with_flag_can_fail_over_to_gemini():
    ollama = FakeProvider("ollama", [ProviderError("down")])
    gemini = FakeProvider("gemini", ['{"skills": ["seen"]}'])
    svc = service(make_settings(vision_fallback_to_gemini=True), ollama, gemini)
    result = await analyze_images(svc, [b"jpeg-bytes"], "check the seam", Skills)
    assert result.source == "gemini"


# --- translation never falls over to the local model; Gemini retries once ----------


def test_translation_stays_on_its_provider():
    """A 3B local model mistranslates Hindi and Marathi without any sign of it, so it is never the backup."""
    assert provider_order(make_settings(), Task.TRANSLATION) == ["gemini"]
    assert provider_order(make_settings(llm_route_translation="ollama"), Task.TRANSLATION) == ["ollama"]


async def test_a_failed_translation_uses_the_rule_fallback_not_the_local_model():
    ollama = FakeProvider("ollama", ['{"skills": ["wrong"]}'])
    gemini = FakeProvider("gemini", [ProviderError("down")])
    svc = service(make_settings(), ollama, gemini)
    result = await svc.generate(req(Task.TRANSLATION), Skills, fallback=lambda: Skills(skills=["original"]))
    assert result.source == "fallback" and result.value.skills == ["original"]
    assert ollama.calls == 0


class _Resp:
    def __init__(self, status: int, body: dict | None = None) -> None:
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self) -> None:
        import httpx

        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"), response=httpx.Response(self.status_code))

    def json(self) -> dict:
        return self._body


def _fake_client(statuses: list[int], calls: list[int]):
    ok = {"candidates": [{"content": {"parts": [{"text": '{"skills": []}'}]}}]}

    class Client:
        def __init__(self, *a, **k) -> None: ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def post(self, *a, **k):
            status = statuses.pop(0)
            calls.append(status)
            return _Resp(status, ok if status == 200 else None)

    return Client


@pytest.mark.parametrize("first", [429, 503])
async def test_gemini_retries_once_on_a_rate_limit_or_overload(monkeypatch, first):
    from app.services import llm as llm_mod

    calls: list[int] = []
    monkeypatch.setattr(llm_mod, "GEMINI_RETRY_PAUSE_S", 0)
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", _fake_client([first, 200], calls))
    provider = llm_mod.GeminiProvider("key", "m", "", "http://x", 5)
    assert await provider.complete(req()) == '{"skills": []}'
    assert calls == [first, 200]


async def test_gemini_does_not_retry_a_bad_request(monkeypatch):
    from app.services import llm as llm_mod

    calls: list[int] = []
    monkeypatch.setattr(llm_mod, "GEMINI_RETRY_PAUSE_S", 0)
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", _fake_client([400, 200], calls))
    provider = llm_mod.GeminiProvider("key", "m", "", "http://x", 5)
    with pytest.raises(ProviderError):
        await provider.complete(req())
    assert calls == [400]


async def test_gemini_gives_up_after_two_tries(monkeypatch):
    from app.services import llm as llm_mod

    calls: list[int] = []
    monkeypatch.setattr(llm_mod, "GEMINI_RETRY_PAUSE_S", 0)
    monkeypatch.setattr(llm_mod.httpx, "AsyncClient", _fake_client([503, 503, 200], calls))
    provider = llm_mod.GeminiProvider("key", "m", "", "http://x", 5)
    with pytest.raises(ProviderError):
        await provider.complete(req())
    assert calls == [503, 503]
