"""Authentication: OTP login, and token issue and rotation.

Collections: users, otp_requests, refresh_tokens. Every secret is stored hashed:
OTPs (keyed HMAC) and refresh tokens (SHA-256).
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app import security, timeutil
from app.config import Settings
from app.errors import ApiError
from app.models.auth import Preferences

WINDOW = timedelta(minutes=10)


# ---------------------------------------------------------------------------
# Demo login policy
# ---------------------------------------------------------------------------


def demo_phone_allowed(settings: Settings, phone: str) -> bool:
    if settings.demo_allow_any_number:
        return True
    allowed = {p.strip() for p in settings.demo_phones.split(",") if p.strip()}
    if "*" in allowed:
        return True
    return phone in {security.normalize_phone(p) for p in allowed}


def admin_phone(settings: Settings, phone: str) -> bool:
    """Admin comes only from the ADMIN_PHONES setting, never from a request. A wildcard is not honoured.
    While any number may sign in with the shared demo code, nobody can become admin by phone number: typing a number
    and the code is all it would take."""
    if settings.demo_allow_any_number:
        return False
    listed = {security.normalize_phone(p) for p in settings.admin_phones.split(",") if p.strip() and p.strip() != "*"}
    return phone in listed


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


async def request_otp(db: AsyncIOMotorDatabase, settings: Settings, phone_raw: str, ip: str) -> dict[str, int]:
    phone = security.normalize_phone(phone_raw)
    if phone is None:
        raise ApiError(422, "invalid_phone", "That is not a valid mobile number.", "Enter a 10-digit Indian mobile number.")
    if not settings.demo_mode:
        # No SMS gateway is built. Production needs a paid gateway and registered templates.
        raise ApiError(501, "sms_not_configured", "SMS login is not set up.", "Use demo mode for now.")
    if not demo_phone_allowed(settings, phone):
        raise ApiError(403, "number_not_allowed", "This number is not allowed in demo mode.", "Ask the team to add it to the demo list.")

    now = timeutil.utcnow()
    h = security.phone_hash(settings, phone)
    col = db["otp_requests"]

    recent = await col.find_one({"phone_hash": h}, sort=[("created_at", -1)])
    if recent is not None:
        wait = settings.otp_resend_cooldown_s - (now - timeutil.ensure_aware(recent["created_at"])).total_seconds()
        if wait > 0:
            raise ApiError(429, "otp_cooldown", "Please wait before asking for another code.", "Try again shortly.", retry_after=int(wait) + 1)

    since = now - WINDOW
    if await col.count_documents({"phone_hash": h, "created_at": {"$gte": since}}) >= settings.otp_per_phone_per_10min:
        raise ApiError(429, "too_many_requests", "Too many codes requested for this number.", "Try again in a few minutes.")
    if await col.count_documents({"ip": ip, "created_at": {"$gte": since}}) >= settings.otp_per_ip_per_10min:
        raise ApiError(429, "too_many_requests", "Too many requests from this device.", "Try again in a few minutes.")

    code = settings.demo_otp  # demo mode only; a real gateway would use security.generate_otp()
    await col.insert_one(
        {
            "_id": uuid.uuid4().hex,
            "phone_hash": h,
            "ip": ip,
            "otp_hash": security.otp_hash(settings, h, code),
            "attempts": 0,
            "consumed": False,
            "created_at": now,
            "expires_at": now + timedelta(seconds=settings.otp_ttl_s),
        }
    )
    return {"expires_in": settings.otp_ttl_s, "resend_after": settings.otp_resend_cooldown_s}


_BAD_CODE = ApiError(401, "invalid_otp", "That code is not correct or has expired.", "Check the code or ask for a new one.")


async def verify_otp(db: AsyncIOMotorDatabase, settings: Settings, phone_raw: str, otp: str) -> dict[str, Any]:
    """Return the user document on success. Every failure looks the same to the caller."""
    phone = security.normalize_phone(phone_raw)
    if phone is None:
        raise ApiError(422, "invalid_phone", "That is not a valid mobile number.", "Enter a 10-digit Indian mobile number.")
    now = timeutil.utcnow()
    h = security.phone_hash(settings, phone)
    col = db["otp_requests"]

    latest = await col.find_one({"phone_hash": h, "consumed": False, "expires_at": {"$gt": now}}, sort=[("created_at", -1)])
    if latest is None:
        raise _BAD_CODE

    # Count the attempt first, atomically, so parallel guesses cannot beat the limit.
    attempt = await col.find_one_and_update(
        {"_id": latest["_id"], "consumed": False, "attempts": {"$lt": settings.otp_max_attempts}},
        {"$inc": {"attempts": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if attempt is None:
        raise ApiError(429, "otp_attempts_exceeded", "Too many wrong codes.", "Ask for a new code.")

    if not security.constant_time_equal(attempt["otp_hash"], security.otp_hash(settings, h, otp)):
        raise _BAD_CODE

    # Single use: only one verification can flip `consumed`.
    flipped = await col.update_one({"_id": attempt["_id"], "consumed": False}, {"$set": {"consumed": True}})
    if flipped.modified_count != 1:
        raise _BAD_CODE

    user = await db["users"].find_one_and_update(
        {"phone_hash": h},
        {
            "$setOnInsert": {
                "_id": uuid.uuid4().hex,
                "phone_enc": security.encrypt_phone(settings, phone),
                "roles": [],
                "language": "en",
                "preferences": Preferences().model_dump(),
                "created_at": now,
            },
            "$set": {"last_login": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if admin_phone(settings, phone) and "admin" not in user.get("roles", []):
        user = await db["users"].find_one_and_update({"_id": user["_id"]}, {"$addToSet": {"roles": "admin"}}, return_document=ReturnDocument.AFTER)
    return user


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


async def issue_tokens(db: AsyncIOMotorDatabase, settings: Settings, user: dict[str, Any], family_id: str | None = None) -> dict[str, Any]:
    access, expires_in = security.create_access_token(settings, user["_id"], user.get("roles", []))
    plain, token_hash = security.new_refresh_token()
    now = timeutil.utcnow()
    await db["refresh_tokens"].insert_one(
        {
            "_id": uuid.uuid4().hex,
            "token_hash": token_hash,
            "user_id": user["_id"],
            "family_id": family_id or uuid.uuid4().hex,
            "created_at": now,
            "expires_at": now + timedelta(days=settings.refresh_token_days),
            "used_at": None,
        }
    )
    return {"access_token": access, "refresh_token": plain, "expires_in": expires_in}


_BAD_REFRESH = ApiError(401, "invalid_refresh_token", "Your session has ended.", "Sign in again.")


async def rotate_refresh(db: AsyncIOMotorDatabase, settings: Settings, plain: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exchange a refresh token for a new pair. Presenting a used token revokes the whole family."""
    now = timeutil.utcnow()
    col = db["refresh_tokens"]
    token_hash = security.hash_refresh_token(plain)

    record = await col.find_one({"token_hash": token_hash})
    if record is None or timeutil.ensure_aware(record["expires_at"]) <= now:
        raise _BAD_REFRESH

    claimed = await col.find_one_and_update(
        {"_id": record["_id"], "used_at": None}, {"$set": {"used_at": now}}, return_document=ReturnDocument.AFTER
    )
    if claimed is None:
        # Already rotated: either a replay or a stolen copy. End every session in this family.
        await col.delete_many({"family_id": record["family_id"]})
        raise _BAD_REFRESH

    user = await db["users"].find_one({"_id": record["user_id"]})
    if user is None:
        raise _BAD_REFRESH
    tokens = await issue_tokens(db, settings, user, family_id=record["family_id"])
    return user, tokens


async def revoke_refresh(db: AsyncIOMotorDatabase, plain: str) -> None:
    await db["refresh_tokens"].delete_many({"token_hash": security.hash_refresh_token(plain)})


# ---------------------------------------------------------------------------
# User view
# ---------------------------------------------------------------------------


async def user_view(db: AsyncIOMotorDatabase, user: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    roles = user.get("roles", [])
    profile = None
    if "student" in roles and await db["student_profiles"].find_one({"user_id": user["_id"]}, {"_id": 1}):
        profile = "student"
    elif "teacher" in roles and await db["teacher_profiles"].find_one({"user_id": user["_id"]}, {"_id": 1}):
        profile = "teacher"
    return {
        "id": user["_id"],
        "roles": roles,
        "language": user.get("language", "en"),
        "profile": profile,
        "preferences": user.get("preferences") or Preferences().model_dump(),
        "phone": security.decrypt_phone(settings, user["phone_enc"]) if settings and user.get("phone_enc") else None,
    }
