from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, require_role
from app.models.mentoring import EvidenceDecisionIn
from app.services import teacher_assessment

router = APIRouter(prefix="/admin", tags=["admin"])
admin = Depends(require_role("admin"))


@router.get("/teachers/pending")
async def pending_teachers(user: dict[str, Any] = admin, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return {"teachers": await teacher_assessment.pending_review(db)}


@router.post("/teachers/{teacher_id}/verify")
async def verify_teacher(teacher_id: str, body: EvidenceDecisionIn, user: dict[str, Any] = admin, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await teacher_assessment.review_evidence(db, user, teacher_id, body.decision, body.note.strip())
