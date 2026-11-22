from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.deps import current_user
from app.errors import ApiError
from app.services import assessments, catalog

router = APIRouter(prefix="/careers", tags=["careers"])


@router.get("")
async def list_careers(_: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """The whole catalogue (cards only). The ranked list a learner sees comes from /assessments."""
    return {"careers": [assessments.career_card(c) for c in catalog.careers()]}


@router.get("/{career_id}")
async def get_career(career_id: str, _: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    career = catalog.career(career_id)
    if career is None:
        raise ApiError(404, "career_not_found", "We could not find that career.", "Pick one from your list.")
    return assessments.career_detail(career)
