from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.deps import get_db, require_role
from app.models.opportunities import ApplicationPatch, OpportunityCheckIn
from app.services import opportunities, packs

router = APIRouter(tags=["opportunities"])
student = Depends(require_role("student"))
teacher = Depends(require_role("teacher"))


@router.post("/journeys/{journey_id}/complete")
async def complete(journey_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await opportunities.complete(db, user, journey_id)


@router.get("/opportunities")
async def list_opportunities(
    user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    """The top 3 and the rest, for the learner's finished path. Eligibility is decided by the rules engine."""
    return await opportunities.listing(db, user, settings)


@router.post("/opportunities/check")
async def check_opportunities(
    body: OpportunityCheckIn,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """The same list, checked again with a few answers from the learner. The answers are used for this call only."""
    return await opportunities.listing(db, user, settings, body.facts.model_dump(exclude_none=True))


@router.post("/opportunities/{opportunity_id}/apply", status_code=201)
async def apply(
    opportunity_id: str,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return {"application": await opportunities.apply(db, user, opportunity_id, settings)}


@router.get("/applications/me")
async def my_applications(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await opportunities.my_applications(db, user)


@router.patch("/applications/{application_id}")
async def patch_application(
    application_id: str, body: ApplicationPatch, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict[str, Any]:
    return {"application": await opportunities.update_status(db, user, application_id, body.status)}


@router.get("/teachers/me/applications")
async def teacher_applications(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await opportunities.teacher_applications(db, user)


@router.post("/applications/{application_id}/assist")
async def assist(application_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return {"application": await opportunities.assist(db, user, application_id)}


@router.get("/careers/{career_id}/pack")
async def career_pack(career_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    """The job knowledge pack. Only a learner who finished this path can open it."""
    return await packs.build(db, user, career_id)
