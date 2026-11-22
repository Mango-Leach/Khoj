from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import current_user, get_db
from app.models.auth import PreferencesPatch, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
async def me(user: dict[str, Any] = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await auth_service.user_view(db, user)


@router.patch("/preferences", response_model=UserOut)
async def update_preferences(
    body: PreferencesPatch,
    user: dict[str, Any] = Depends(current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if body.language is not None:
        changes["language"] = body.language
    if body.channels is not None:
        changes["preferences.channels"] = body.channels.model_dump()
    if body.quiet_hours is not None:
        changes["preferences.quiet_hours"] = body.quiet_hours.model_dump()
    if changes:
        await db["users"].update_one({"_id": user["_id"]}, {"$set": changes})
        user = await db["users"].find_one({"_id": user["_id"]})
    return await auth_service.user_view(db, user)
