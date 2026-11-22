from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, require_role
from app.models.calls import BookIn, CallSettingsIn, FeedbackIn, SlotIn
from app.services import calls

router = APIRouter(tags=["calls"])
student = Depends(require_role("student"))
teacher = Depends(require_role("teacher"))


@router.get("/calls")
async def open_calls(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.overview(db, user)


@router.post("/calls/{slot_id}/book")
async def book_call(slot_id: str, body: BookIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.book(db, user, slot_id, body)


@router.post("/calls/{slot_id}/cancel")
async def cancel_call(slot_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.cancel(db, user, slot_id)


@router.post("/calls/{slot_id}/feedback")
async def call_feedback(slot_id: str, body: FeedbackIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.feedback(db, user, slot_id, body)


@router.get("/teachers/me/calls")
async def my_calls(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.host_overview(db, user)


@router.patch("/teachers/me/calls")
async def my_calls_settings(body: CallSettingsIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.set_offering(db, user, body.offers_calls)


@router.post("/teachers/me/calls/slots", status_code=201)
async def add_call_slot(body: SlotIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.add_slot(db, user, body)


@router.post("/teachers/me/calls/slots/{slot_id}/cancel")
async def cancel_call_slot(slot_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await calls.host_cancel(db, user, slot_id)
