from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import current_user, get_db, get_llm, require_role
from app.models.mentoring import CredentialIn, TestSubmitIn
from app.models.profiles import TeacherProfileIn, TeacherProfilePatch
from app.services import images, profiles, proof_review, teacher_assessment
from app.services.llm import LLMService

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.post("/profile", status_code=201)
async def create_profile(
    body: TeacherProfileIn,
    user: dict[str, Any] = Depends(current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    return await profiles.create_teacher(db, user, body)


@router.get("/me")
async def get_me(user: dict[str, Any] = Depends(require_role("teacher")), db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await profiles.get_teacher(db, user)


@router.patch("/me")
async def patch_me(
    body: TeacherProfilePatch,
    user: dict[str, Any] = Depends(require_role("teacher")),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    return await profiles.update_teacher(db, user, body)


teacher = Depends(require_role("teacher"))


@router.post("/me/credentials", status_code=201)
async def add_credential(body: CredentialIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await teacher_assessment.add_credential(db, user, body)


@router.get("/me/assessments")
async def list_assessments(user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return {"areas": await teacher_assessment.areas_view(db, user)}


@router.get("/me/assessments/{area_id}")
async def get_assessment(area_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await teacher_assessment.area_for_test(db, user, area_id)


@router.post("/me/assessments/{area_id}/submit")
async def submit_assessment(area_id: str, body: TestSubmitIn, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    return await teacher_assessment.submit_test(db, user, area_id, body.scores)


@router.post("/me/credentials/{credential_id}/photos", status_code=201)
async def add_proof_photo(
    credential_id: str,
    file: UploadFile = File(...),
    user: dict[str, Any] = teacher,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    data = await file.read(images.MAX_UPLOAD_BYTES + 1)  # never read more than the limit plus one byte
    return await proof_review.add_photo(db, user, credential_id, data)


@router.get("/me/credentials/{credential_id}/photos/{photo_id}")
async def get_proof_photo(credential_id: str, photo_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    data = await proof_review.get_photo(db, user, credential_id, photo_id)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/me/credentials/{credential_id}/photos/{photo_id}", status_code=204)
async def delete_proof_photo(credential_id: str, photo_id: str, user: dict[str, Any] = teacher, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    await proof_review.delete_photo(db, user, credential_id, photo_id)
    return Response(status_code=204)


@router.post("/me/proof/review", status_code=202)
async def review_proof(
    background: BackgroundTasks,
    user: dict[str, Any] = teacher,
    db: AsyncIOMotorDatabase = Depends(get_db),
    llm: LLMService = Depends(get_llm),
) -> dict[str, Any]:
    """Starts the photo review and returns at once. The page polls `GET /teachers/me` until the status changes."""
    started = await proof_review.start_review(db, user)
    background.add_task(proof_review.run_review, db, llm, user["_id"])
    return started
