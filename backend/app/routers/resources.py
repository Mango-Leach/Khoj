from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.deps import current_user
from app.services import resources

router = APIRouter(tags=["resources"])


@router.get("/resources")
async def list_resources(career_id: str | None = None, _: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Courses and learning material to link out to, optionally for one career."""
    return {"resources": resources.listing(career_id)}
