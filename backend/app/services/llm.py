"""LLM layer: Ollama and Gemini behind one interface, routed per task with failover.

Failover chain for every call:
    cache -> primary provider -> the other provider -> rule-based fallback
A provider is abandoned on a timeout, a provider error, or output that still fails
schema validation after one retry. In `cache_only` mode no provider is ever called.

PRIVACY: callers must never put names, phone numbers or exact locations in a request.
Send IDs and age bands only (CLAUDE.md, "Guardrails").
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import ProviderName, Settings
from app.services.cache import Cache

log = logging.getLogger("khoj.llm")

T = TypeVar("T", bound=BaseModel)


class Task(str, Enum):
    EXTRACTION = "extraction"  # transcript -> skills, interests, constraints (student data)
    DRAFTING = "drafting"  # assignments, review-assist drafts, nudges
    REASONING = "reasoning"  # career reasons, dashboard summaries
    TRANSLATION = "translation"  # native-language answer -> English (the reasoning pivot)
    INGESTION = "ingestion"  # knowledge-hub classification, course packs, cache warming (no student data)
    VISION = "vision"  # practical-work photo review (student photos: stay on the laptop by default)
    PROOF = "proof"  # a teacher's proof photos (certificates, work samples); adults' documents, read by Gemini by default


class ProviderError(Exception):
    """Transport, timeout, auth, or configuration problem with one provider."""


class LLMUnavailable(Exception):
    """Every provider failed and no fallback was supplied."""


@dataclass
class LLMRequest:
    task: Task
    prompt: str
    system: str = ""
    schema: dict[str, Any] | None = None  # JSON schema, used by providers that support it
    temperature: float = 0.2
    prompt_version: str = "v1"
    images: list[bytes] = field(default_factory=list)


class LLMProvider(Protocol):
    name: ProviderName

    def model_for(self, req: LLMRequest) -> str: ...

    async def complete(self, req: LLMRequest) -> str: ...


@dataclass
class LLMResult(Generic[T]):
    value: T
    source: str  # "cache" | "ollama" | "gemini" | "fallback"
    model: str = ""
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class OllamaProvider:
    name: ProviderName = "ollama"

    def __init__(self, host: str, text_model: str, vision_model: str, timeout_s: float) -> None:
        self.host = host.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model
        self.timeout_s = timeout_s

    def model_for(self, req: LLMRequest) -> str:
        return self.vision_model if req.images else self.text_model

    async def complete(self, req: LLMRequest) -> str:
        model = self.model_for(req)
        if not model:
            raise ProviderError("ollama model not configured")
        messages: list[dict[str, Any]] = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        user: dict[str, Any] = {"role": "user", "content": req.prompt}
        if req.images:
            user["images"] = [base64.b64encode(i).decode("ascii") for i in req.images]
        messages.append(user)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": req.schema or "json",
            "options": {"temperature": req.temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.host}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"ollama: {type(exc).__name__}: {exc}") from exc


GEMINI_ATTEMPTS = 2  # the free tier answers 429 and 503 now and then; one quick retry clears most of them
GEMINI_RETRY_PAUSE_S = 1.5


def _transient(exc: Exception) -> bool:
    """Worth one more try: rate limits, overload, network trouble. A bad key or a bad request is not."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (408, 429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


class GeminiProvider:
    name: ProviderName = "gemini"

    def __init__(self, api_key: str, text_model: str, vision_model: str, base_url: str, timeout_s: float) -> None:
        self.api_key = api_key
        self.text_model = text_model
        self.vision_model = vision_model or text_model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def model_for(self, req: LLMRequest) -> str:
        return self.vision_model if req.images else self.text_model

    async def complete(self, req: LLMRequest) -> str:
        if not self.api_key:
            raise ProviderError("gemini api key not configured")
        model = self.model_for(req)
        if not model:
            raise ProviderError("gemini model not configured")
        parts: list[dict[str, Any]] = [{"text": req.prompt}]
        for image in req.images:
            parts.append({"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(image).decode("ascii")}})
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": req.temperature, "responseMimeType": "application/json"},
        }
        if req.system:
            body["systemInstruction"] = {"parts": [{"text": req.system}]}
        last: Exception | None = None
        for attempt in range(GEMINI_ATTEMPTS):
            if attempt:
                await asyncio.sleep(GEMINI_RETRY_PAUSE_S)
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    # Key goes in a header, never the URL, so it cannot leak into logs.
                    resp = await client.post(
                        f"{self.base_url}/models/{model}:generateContent",
                        json=body,
                        headers={"x-goog-api-key": self.api_key},
                    )
                    resp.raise_for_status()
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                last = exc
                if not _transient(exc):
                    break
        raise ProviderError(f"gemini: {type(last).__name__}") from last


def build_providers(settings: Settings) -> dict[ProviderName, LLMProvider]:
    return {
        "ollama": OllamaProvider(
            settings.ollama_host, settings.ollama_text_model, settings.ollama_vision_model, settings.ollama_timeout_s
        ),
        "gemini": GeminiProvider(
            settings.gemini_api_key,
            settings.gemini_text_model,
            settings.gemini_vision_model,
            settings.gemini_base_url,
            settings.gemini_timeout_s,
        ),
    }


# ---------------------------------------------------------------------------
# Routing and service
# ---------------------------------------------------------------------------


def route_for(settings: Settings, task: Task) -> ProviderName:
    return {
        Task.EXTRACTION: settings.llm_route_extraction,
        Task.DRAFTING: settings.llm_route_drafting,
        Task.REASONING: settings.llm_route_reasoning,
        Task.TRANSLATION: settings.llm_route_translation,
        Task.INGESTION: settings.llm_route_ingestion,
        Task.VISION: settings.vision_route,
        Task.PROOF: settings.proof_route,
    }[task]


def provider_order(settings: Settings, task: Task) -> list[ProviderName]:
    """Primary first, then the other provider if the task may use it."""
    primary = route_for(settings, task)
    other: ProviderName = "gemini" if primary == "ollama" else "ollama"
    if task is Task.VISION and other == "gemini" and not settings.vision_fallback_to_gemini:
        return [primary]  # student photos stay on the laptop unless explicitly allowed
    if task is Task.TRANSLATION:
        # A small local model returns confident but wrong English for Hindi and Marathi, and nothing
        # marks it wrong. Better to keep the learner's own words and say "not translated".
        return [primary]
    return [primary, other]


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_output(text: str, model_cls: type[T]) -> T:
    """Strip optional code fences, parse, and validate. Raises ValueError/ValidationError."""
    cleaned = _FENCE.sub("", text.strip())
    return model_cls.model_validate(json.loads(cleaned))


def cache_key(req: LLMRequest, model_cls: type[BaseModel]) -> str:
    h = hashlib.sha256()
    for part in (req.task.value, req.prompt_version, model_cls.__name__, req.system, req.prompt):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    for image in req.images:
        h.update(hashlib.sha256(image).digest())
    return h.hexdigest()


class LLMService:
    def __init__(self, settings: Settings, providers: dict[ProviderName, LLMProvider], cache: Cache) -> None:
        self.settings = settings
        self.providers = providers
        self.cache = cache

    async def generate(
        self,
        req: LLMRequest,
        model_cls: type[T],
        fallback: Callable[[], T] | None = None,
    ) -> LLMResult[T]:
        key = cache_key(req, model_cls)

        cached = await self._cache_get(key)
        if cached is not None:
            try:
                value = model_cls.model_validate(cached["value"])
                self._log(req, "cache", cached.get("model", ""), 0, cache_hit=True)
                return LLMResult(value, "cache", cached.get("model", ""), 0)
            except ValidationError:
                log.warning("cached entry failed validation; ignoring", extra={"task": req.task.value})

        if self.settings.llm_mode == "live":
            for name in provider_order(self.settings, req.task):
                result = await self._try_provider(self.providers[name], req, model_cls)
                if result is not None:
                    value, model, latency = result
                    await self._cache_set(key, {"value": value.model_dump(mode="json"), "model": model})
                    return LLMResult(value, name, model, latency)

        if fallback is not None:
            self._log(req, "fallback", "", 0, cache_hit=False)
            return LLMResult(fallback(), "fallback")
        raise LLMUnavailable(f"no provider produced valid output for task {req.task.value}")

    async def _try_provider(
        self, provider: LLMProvider, req: LLMRequest, model_cls: type[T]
    ) -> tuple[T, str, int] | None:
        model = provider.model_for(req)
        for attempt in (1, 2):  # one retry, only for invalid output
            started = time.perf_counter()
            try:
                text = await provider.complete(req)
            except ProviderError as exc:
                log.warning("provider failed", extra={"provider": provider.name, "task": req.task.value, "error": str(exc)})
                return None
            latency = int((time.perf_counter() - started) * 1000)
            try:
                value = parse_json_output(text, model_cls)
            except (ValueError, ValidationError) as exc:
                log.warning(
                    "invalid output",
                    extra={"provider": provider.name, "task": req.task.value, "attempt": attempt, "error": type(exc).__name__},
                )
                continue
            self._log(req, provider.name, model, latency, cache_hit=False)
            return value, model, latency
        return None

    async def _cache_get(self, key: str) -> dict[str, Any] | None:
        try:
            return await self.cache.get(key)
        except Exception as exc:  # a broken cache must never break a request
            log.warning("cache read failed", extra={"error": type(exc).__name__})
            return None

    async def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        try:
            await self.cache.set(key, value)
        except Exception as exc:
            log.warning("cache write failed", extra={"error": type(exc).__name__})

    @staticmethod
    def _log(req: LLMRequest, source: str, model: str, latency_ms: int, cache_hit: bool) -> None:
        log.info(
            "llm call",
            extra={
                "task": req.task.value,
                "prompt_version": req.prompt_version,
                "provider": source,
                "model": model,
                "latency_ms": latency_ms,
                "cache_hit": cache_hit,
            },
        )
