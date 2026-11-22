from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.deps import get_db, require_role
from app.services import schemes

router = APIRouter(tags=["scholarships"])
student = Depends(require_role("student"))


@router.get("/scholarships")
async def list_scholarships(_: dict[str, Any] = student) -> dict[str, Any]:
    """Every scheme with its source and verification label. No eligibility here: that needs the check below."""
    return {"schemes": schemes.list_schemes()}


@router.post("/scholarships/check")
async def check_scholarships(
    body: schemes.SchemeCheckIn,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Checks the learner against the rule files. Age, class and state come from the saved profile.
    The answers in the body are used for this call only and are not stored."""
    return await schemes.check(db, user, body, settings)
