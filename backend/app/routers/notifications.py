from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import current_user, get_db
from app.services import notifications

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(user: dict[str, Any] = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await notifications.list_for(db, user)


@router.get("/notifications/unread")
async def unread(user: dict[str, Any] = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, int]:
    return {"unread": await notifications.unread_count(db, user)}


@router.post("/notifications/read-all")
async def read_all(user: dict[str, Any] = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await notifications.mark_all_read(db, user)


@router.post("/notifications/{notification_id}/read")
async def read_one(notification_id: str, user: dict[str, Any] = Depends(current_user), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await notifications.mark_read(db, user, notification_id)
