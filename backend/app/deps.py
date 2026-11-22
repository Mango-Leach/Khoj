"""FastAPI dependencies shared by routers."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import db as db_module
from app import security
from app.config import Settings, get_settings
from app.errors import ApiError
from app.services.cache import build_cache
from app.services.gnani import GnaniClient
from app.services.llm import LLMService, build_providers

_bearer = HTTPBearer(auto_error=False)

_llm_service: LLMService | None = None
_gnani_client: GnaniClient | None = None


def get_llm(settings: Settings = Depends(get_settings)) -> LLMService:
    """One shared LLM service (providers and cache) for the whole process. Tests override this."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(settings, build_providers(settings), build_cache(settings))
    return _llm_service


def get_gnani(settings: Settings = Depends(get_settings)) -> GnaniClient:
    """One shared Gnani client, so the key pool remembers which keys are out of credit. Tests override this."""
    global _gnani_client
    if _gnani_client is None:
        _gnani_client = GnaniClient(settings)
    return _gnani_client


async def get_db() -> AsyncIOMotorDatabase:
    database = db_module.get_database()
    if database is None:
        raise ApiError(503, "db_unavailable", "The database is not set up.", "Set MONGODB_URI and restart.")
    return database


def client_ip(request: Request, settings: Settings = Depends(get_settings)) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    database: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Authenticate the caller. Roles come from the database, not the token, so a role
    change or a deleted account takes effect immediately."""
    if creds is None:
        raise ApiError(401, "not_authenticated", "Please sign in.", "")
    claims = security.decode_access_token(settings, creds.credentials)
    user = await database["users"].find_one({"_id": claims["sub"]})
    if user is None:
        raise ApiError(401, "invalid_token", "This session is not valid.", "Sign in again.")
    return user


def require_role(role: str):
    async def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if role not in user.get("roles", []):
            raise ApiError(403, "wrong_role", "This is not available for your account.", "")
        return user

    return dependency
