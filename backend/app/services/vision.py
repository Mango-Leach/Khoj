"""Vision (practical-work photo review) goes through the same routed, cached LLM service.

Images are routed to Ollama by default. Gemini is only used when `VISION_ROUTE=gemini`
or `VISION_FALLBACK_TO_GEMINI=true`, because student photos then leave the laptop.
"""
from __future__ import annotations

from typing import Callable, TypeVar

from pydantic import BaseModel

from app.services.llm import LLMRequest, LLMResult, LLMService, Task

T = TypeVar("T", bound=BaseModel)


async def analyze_images(
    service: LLMService,
    images: list[bytes],
    prompt: str,
    model_cls: type[T],
    *,
    system: str = "",
    schema: dict | None = None,
    prompt_version: str = "v1",
    fallback: Callable[[], T] | None = None,
    task: Task = Task.VISION,
) -> LLMResult[T]:
    """Run a vision analysis. The fallback should route the submission to a teacher."""
    req = LLMRequest(
        task=task,
        prompt=prompt,
        system=system,
        schema=schema,
        prompt_version=prompt_version,
        images=images,
    )
    return await service.generate(req, model_cls, fallback=fallback)
