from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, get_llm, require_role
from app.services import assessments
from app.services.llm import LLMService

router = APIRouter(tags=["assessments"])
student = Depends(require_role("student"))


@router.post("/assessments", status_code=202)
async def create_assessment(
    background: BackgroundTasks,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    llm: LLMService = Depends(get_llm),
) -> dict[str, Any]:
    """Ranks the careers now (plain code, instant). Nicer one-sentence reasons are written afterwards;
    the client polls `GET /assessments/{id}` and sees `enrichment` change from pending to done."""
    view = await assessments.create(db, user)
    background.add_task(assessments.enrich, db, llm, view["id"], user["_id"])
    return view


@router.get("/assessments/latest")
async def latest_assessment(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assessments.latest(db, user)


@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assessments.get(db, user, assessment_id)


@router.post("/careers/{career_id}/select", status_code=201)
async def select_career(career_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assessments.select_career(db, user, career_id)
