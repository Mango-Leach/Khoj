from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app import db
from app.config import get_settings
from app.errors import ApiError, api_error_handler, validation_error_handler
from app.indexes import ensure_indexes
from app.routers import admin, assessments, assignments, auth, calls, careers, catalog, health, intake, me, mentoring, notifications, opportunities, peers, resources, scholarships, students, teachers, voice
from app.security import assert_secrets_ok
from app.services.cache import build_cache
from app.services.llm import LLMService, build_providers

log = logging.getLogger("khoj")


@lru_cache
def get_llm_service() -> LLMService:
    settings = get_settings()
    return LLMService(settings, build_providers(settings), build_cache(settings))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    assert_secrets_ok(settings)
    if settings.demo_mode and ("*" in settings.demo_phones or settings.demo_allow_any_number):
        log.warning("Any number can sign in with the shared demo code. Use this for a local demo only.")
    database = db.get_database(settings)
    if database is not None:
        try:
            await ensure_indexes(database)
        except Exception as exc:  # the API should still start; /health shows the database state
            log.warning("could not create indexes: %s", type(exc).__name__)
    yield
    db.close_client()


app = FastAPI(title="KHOJ API", version="0.2.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

for router in (health.router, auth.router, me.router, students.router, teachers.router, catalog.router, intake.router, voice.router, careers.router, assessments.router, scholarships.router, resources.router, mentoring.router, calls.router, peers.router, assignments.router, opportunities.router, notifications.router, admin.router):
    app.include_router(router, prefix="/api/v1")
