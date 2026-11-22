from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db, get_llm, require_role
from app.models.intake import AcceptIn, ConfirmIn, SessionCreate
from app.services import catalog, intake
from app.services.llm import LLMService

router = APIRouter(prefix="/intake", tags=["intake"])

# Voice intake belongs to students. Every call is scoped to the caller inside the service.
student = Depends(require_role("student"))


@router.get("/questions")
async def list_questions(_: dict[str, Any] = student) -> dict[str, Any]:
    """The seven questions, each in English, Hindi and Marathi. Choice questions carry their options."""
    return {"questions": catalog.questions()}


@router.post("/sessions", status_code=201)
async def create_session(body: SessionCreate, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await intake.create_session(db, user, body)


@router.get("/sessions/latest")
async def latest_session(user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await intake.latest_session(db, user)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await intake.get_session(db, user, session_id)


@router.get("/sessions/{session_id}/next")
async def next_question(session_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    view = await intake.get_session(db, user, session_id)
    question = catalog.question(view["next_question_id"]) if view["next_question_id"] else None
    answered = len(view["answers"])
    return {"question": question, "number": answered + 1 if question else None, "total": view["total_questions"], "done": question is None}


@router.post("/sessions/{session_id}/confirm")
async def confirm_answer(
    session_id: str,
    body: ConfirmIn,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    llm: LLMService = Depends(get_llm),
) -> dict[str, Any]:
    return await intake.confirm_answer(db, llm, user, session_id, body)


@router.post("/sessions/{session_id}/complete")
async def complete(
    session_id: str,
    user: dict[str, Any] = student,
    db: AsyncIOMotorDatabase = Depends(get_db),
    llm: LLMService = Depends(get_llm),
) -> dict[str, Any]:
    return await intake.complete(db, llm, user, session_id)


@router.post("/sessions/{session_id}/accept")
async def accept(session_id: str, body: AcceptIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await intake.accept(db, user, session_id, body)
