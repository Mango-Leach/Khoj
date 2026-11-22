from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app import db
from app.config import Settings, get_settings
from app.deps import get_gnani
from app.services.gnani import GnaniClient
from app.services.llm import Task, provider_order, route_for

router = APIRouter()


async def _probe_ollama(settings: Settings) -> dict[str, Any]:
    info: dict[str, Any] = {
        "host": settings.ollama_host,
        "text_model_set": bool(settings.ollama_text_model),
        "vision_model_set": bool(settings.ollama_vision_model),
    }
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{settings.ollama_host.rstrip('/')}/api/tags")
            resp.raise_for_status()
        info["reachable"] = True
    except Exception:
        info["reachable"] = False
    return info


# Windows takes about 2 seconds to give up on a closed loopback port, so every probe is
# capped here. A healthy local service answers in milliseconds, so the cap costs nothing.
OLLAMA_PROBE_CAP_S = 1.6  # the probe itself takes ~0.7 s on a cold httpx client on Windows
DB_PROBE_CAP_S = 2.5


async def _capped(coro, cap_s: float, on_timeout):
    try:
        return await asyncio.wait_for(coro, timeout=cap_s)
    except TimeoutError:
        return on_timeout


@router.get("/health")
async def health(settings: Settings = Depends(get_settings), gnani: GnaniClient = Depends(get_gnani)) -> dict[str, Any]:
    """Liveness plus a quick view of what is configured and reachable. Never raises."""
    (db_ok, db_detail), ollama = await asyncio.gather(
        _capped(db.ping(settings), DB_PROBE_CAP_S, (False, "unreachable: timeout")),
        _capped(
            _probe_ollama(settings),
            OLLAMA_PROBE_CAP_S,
            {
                "host": settings.ollama_host,
                "text_model_set": bool(settings.ollama_text_model),
                "vision_model_set": bool(settings.ollama_vision_model),
                "reachable": False,
            },
        ),
    )
    return {
        "status": "ok",
        "env": settings.app_env,
        "demo_mode": settings.demo_mode,
        "db": {"configured": bool(settings.mongodb_uri), "ok": db_ok, "detail": db_detail},
        "llm": {
            "mode": settings.llm_mode,
            "routes": {t.value: route_for(settings, t) for t in Task},
            "vision_order": provider_order(settings, Task.VISION),
            "ollama": ollama,
            "gemini": {"configured": bool(settings.gemini_api_key and settings.gemini_text_model)},
        },
        # how many keys are set and how many can still be used for each service; never the keys themselves
        "speech": {"provider": "gnani", **gnani.pool.status()},
    }
