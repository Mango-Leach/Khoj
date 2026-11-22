from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, require_role
from app.models.peers import MyCardIn, ReportIn
from app.services import peers

router = APIRouter(prefix="/connect", tags=["connect"])
student = Depends(require_role("student"))


@router.get("")
async def connect_overview(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.overview(db, user)


@router.put("/me")
async def set_my_card(body: MyCardIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.set_card(db, user, body)


@router.post("/requests/{request_id}/accept")
async def accept_request(request_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.accept(db, user, request_id)


@router.post("/requests/{request_id}/decline")
async def decline_request(request_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.decline(db, user, request_id)


@router.post("/requests/{request_id}/cancel")
async def cancel_request(request_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.cancel(db, user, request_id)


@router.post("/connections/{connection_id}/remove")
async def remove_connection(connection_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.remove(db, user, connection_id)


@router.post("/{card_id}/request", status_code=201)
async def request_connection(card_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.request(db, user, card_id)


@router.post("/{card_id}/block")
async def block_person(card_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.block(db, user, card_id)


@router.post("/{card_id}/report")
async def report_person(card_id: str, body: ReportIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await peers.report(db, user, card_id, body)
