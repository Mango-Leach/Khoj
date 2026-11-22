from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, require_role
from app.models.mentoring import MentorRequestIn
from app.services import mentoring

router = APIRouter(tags=["mentoring"])
student = Depends(require_role("student"))
teacher = Depends(require_role("teacher"))


@router.get("/journeys/me")
async def my_journey(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.journey_view(db, user)


@router.get("/journeys/{journey_id}/match-mentor")
async def match_mentor(journey_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.candidates(db, user, journey_id)


@router.post("/journeys/{journey_id}/mentor-request", status_code=201)
async def mentor_request(journey_id: str, body: MentorRequestIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.request_mentor(db, user, journey_id, body.teacher_id)


@router.post("/journeys/{journey_id}/mentor-request/cancel")
async def cancel_mentor_request(journey_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.cancel_request(db, user, journey_id)


@router.get("/teachers/me/requests")
async def my_requests(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.teacher_requests(db, user)


@router.get("/teachers/me/students")
async def my_students(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return {"students": await mentoring.my_students(db, user)}


@router.post("/requests/{request_id}/accept")
async def accept(request_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.decide(db, user, request_id, True)


@router.post("/requests/{request_id}/decline")
async def decline(request_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await mentoring.decide(db, user, request_id, False)
