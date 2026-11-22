from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import current_user, get_db, require_role
from app.models.profiles import StudentProfileIn, StudentProfilePatch
from app.services import profiles

router = APIRouter(prefix="/students", tags=["students"])


@router.post("/profile", status_code=201)
async def create_profile(
    body: StudentProfileIn,
    user: dict[str, Any] = Depends(current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    return await profiles.create_student(db, user, body)


@router.get("/me")
async def get_me(user: dict[str, Any] = Depends(require_role("student")), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await profiles.get_student(db, user)


@router.patch("/me")
async def patch_me(
    body: StudentProfilePatch,
    user: dict[str, Any] = Depends(require_role("student")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    return await profiles.update_student(db, user, body)
