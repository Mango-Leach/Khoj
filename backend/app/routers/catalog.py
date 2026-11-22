from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.services import catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    """The eight career families, shown as picture tiles on the skills screen."""
    return {"categories": catalog.categories()}


@router.get("/skills")
async def list_skills() -> dict[str, Any]:
    """The controlled skill vocabulary. Matching keywords stay on the server."""
    return {"skills": [{"id": s["id"], "family": s["family"], "name": s["name"]} for s in catalog.skills()]}


@router.get("/districts")
async def list_districts() -> dict[str, Any]:
    """The 36 Maharashtra districts, named in English, Hindi and Marathi."""
    return {"state": "Maharashtra", "districts": catalog.districts()}
