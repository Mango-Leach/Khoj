from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.deps import client_ip, get_db
from app.models.auth import OtpRequestIn, OtpRequestOut, OtpVerifyIn, RefreshIn, TokenOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", response_model=OtpRequestOut)
async def otp_request(
    body: OtpRequestIn,
    ip: str = Depends(client_ip),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, int]:
    return await auth_service.request_otp(db, settings, body.phone, ip)


@router.post("/otp/verify", response_model=TokenOut)
async def otp_verify(
    body: OtpVerifyIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user = await auth_service.verify_otp(db, settings, body.phone, body.otp)
    tokens = await auth_service.issue_tokens(db, settings, user)
    return {**tokens, "user": await auth_service.user_view(db, user)}


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    body: RefreshIn,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user, tokens = await auth_service.rotate_refresh(db, settings, body.refresh_token)
    return {**tokens, "user": await auth_service.user_view(db, user)}


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, db: AsyncIOMotorDatabase = Depends(get_db)) -> Response:
    await auth_service.revoke_refresh(db, body.refresh_token)
    return Response(status_code=204)
