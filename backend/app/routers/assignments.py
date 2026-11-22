from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import current_user, get_db, get_llm, require_role
from app.models.assignments import AckIn, AssignmentIn, AssignmentPatch, ReviewIn, SubmissionIn
from app.services import assignments, images, submissions
from app.services.llm import LLMService

router = APIRouter(tags=["assignments"])
student = Depends(require_role("student"))
teacher = Depends(require_role("teacher"))
anyone = Depends(current_user)  # the service decides which side of the journey the caller is on


# --- milestones and assignments ------------------------------------------------------------------------------------


@router.get("/journeys/{journey_id}/milestones")
async def milestones(journey_id: str, user: dict[str, Any] = anyone, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assignments.milestones_view(db, user, journey_id)


@router.post("/journeys/{journey_id}/milestones/{milestone}/assignments:draft", status_code=201)
async def draft_assignments(
    journey_id: str,
    milestone: str,
    user: dict[str, Any] = teacher,
    db: AsyncIOMotorDatabase = Depends(get_db),
    llm: LLMService = Depends(get_llm),
) -> dict[str, Any]:
    return {"assignments": await assignments.draft_with_ai(db, llm, user, journey_id, milestone)}


@router.post("/journeys/{journey_id}/milestones/{milestone}/assignments", status_code=201)
async def create_assignment(journey_id: str, milestone: str, body: AssignmentIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assignments.create_manual(db, user, journey_id, milestone, body)


@router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: str, user: dict[str, Any] = anyone, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.assignment_detail(db, user, assignment_id)


@router.patch("/assignments/{assignment_id}")
async def patch_assignment(assignment_id: str, body: AssignmentPatch, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await assignments.patch(db, user, assignment_id, body)


# --- the learner's work ---------------------------------------------------------------------------------------------


@router.post("/assignments/{assignment_id}/submissions")
async def save_work(assignment_id: str, body: SubmissionIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.start_or_save(db, user, assignment_id, body)


@router.patch("/submissions/{submission_id}")
async def edit_work(submission_id: str, body: SubmissionIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.edit_draft(db, user, submission_id, body)


@router.post("/submissions/{submission_id}/photos", status_code=201)
async def add_photo(submission_id: str, file: UploadFile = File(...), user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    data = await file.read(images.MAX_UPLOAD_BYTES + 1)  # never read more than the limit plus one byte
    return await submissions.add_photo(db, user, submission_id, data)


@router.get("/submissions/{submission_id}/photos/{photo_id}")
async def get_photo(submission_id: str, photo_id: str, user: dict[str, Any] = anyone, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    data = await submissions.get_photo(db, user, submission_id, photo_id)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/submissions/{submission_id}/photos/{photo_id}", status_code=204)
async def delete_photo(submission_id: str, photo_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    await submissions.delete_photo(db, user, submission_id, photo_id)
    return Response(status_code=204)


@router.post("/submissions/{submission_id}/send")
async def send_work(submission_id: str, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db), llm: LLMService = Depends(get_llm)) -> dict[str, Any]:
    return await submissions.send(db, llm, user, submission_id)


@router.post("/submissions/{submission_id}/ack")
async def ack(submission_id: str, body: AckIn, user: dict[str, Any] = student, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.acknowledge(db, user, submission_id, body.answer)


@router.get("/submissions/{submission_id}")
async def get_submission(submission_id: str, user: dict[str, Any] = anyone, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.get_submission(db, user, submission_id)


# --- the mentor's review --------------------------------------------------------------------------------------------


@router.get("/teachers/me/review-queue")
async def review_queue(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.review_queue(db, user)


@router.post("/submissions/{submission_id}/ai-draft")
async def ai_draft(submission_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db), llm: LLMService = Depends(get_llm)) -> dict[str, Any]:
    return await submissions.ai_draft(db, llm, user, submission_id)


@router.post("/submissions/{submission_id}/review")
async def review(submission_id: str, body: ReviewIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await submissions.review(db, user, submission_id, body)
