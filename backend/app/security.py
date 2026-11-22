"""Security primitives: phone handling, OTP and token hashing, JWTs.

Nothing here touches the database, and nothing logs a phone number or OTP.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings
from app.errors import ApiError
from app import timeutil

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

INSECURE_SECRETS = {"", "change-me"}


def assert_secrets_ok(settings: Settings) -> None:
    """Refuse to run with the placeholder secret anywhere but local dev."""
    if settings.app_env != "dev" and (settings.jwt_secret in INSECURE_SECRETS or len(settings.jwt_secret) < 32):
        raise RuntimeError("JWT_SECRET must be a random secret of at least 32 characters when APP_ENV is not 'dev'")


def _derive(settings: Settings, label: bytes) -> bytes:
    """Independent keys from one master secret, so a leak of one use does not expose another."""
    return hmac.new(settings.jwt_secret.encode("utf-8"), label, hashlib.sha256).digest()


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------

_PHONE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")


def normalize_phone(raw: str) -> str | None:
    """Indian mobile numbers only. Returns +91XXXXXXXXXX, or None if it does not look valid."""
    cleaned = re.sub(r"[\s\-()]", "", raw or "")
    match = _PHONE.match(cleaned)
    return f"+91{match.group(1)}" if match else None


def phone_hash(settings: Settings, phone: str) -> str:
    """Stable lookup key (unique index). Keyed, so it cannot be reversed by enumerating numbers."""
    return hmac.new(_derive(settings, b"phone-hash"), phone.encode("utf-8"), hashlib.sha256).hexdigest()


def _fernet(settings: Settings) -> Fernet:
    key = settings.data_key.encode("utf-8") if settings.data_key else base64.urlsafe_b64encode(_derive(settings, b"fernet"))
    return Fernet(key)


def encrypt_phone(settings: Settings, phone: str) -> str:
    return _fernet(settings).encrypt(phone.encode("utf-8")).decode("ascii")


def decrypt_phone(settings: Settings, token: str) -> str | None:
    try:
        return _fernet(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}XXXXX{phone[-3:]}"


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def otp_hash(settings: Settings, phone_hash_value: str, otp: str) -> str:
    return hmac.new(_derive(settings, b"otp"), f"{phone_hash_value}:{otp}".encode("utf-8"), hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def create_access_token(settings: Settings, user_id: str, roles: list[str]) -> tuple[str, int]:
    """Short-lived JWT. `roles` is informational: the API reads roles from the database."""
    now = timeutil.utcnow()
    ttl = timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {"sub": user_id, "roles": roles, "typ": "access", "iat": now, "exp": now + ttl}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        # Time claims are checked below against app.timeutil, the one clock the app uses, so
        # tests can move it. PyJWT's own checks would read the real clock.
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"], "verify_exp": False, "verify_iat": False},
        )
    except jwt.InvalidTokenError:
        raise ApiError(401, "invalid_token", "This session is not valid.", "Sign in again.")
    if claims.get("typ") != "access":
        raise ApiError(401, "invalid_token", "This session is not valid.", "Sign in again.")
    if claims["exp"] <= timeutil.utcnow().timestamp():
        raise ApiError(401, "token_expired", "Your session has expired.", "Sign in again.")
    return claims


def new_refresh_token() -> tuple[str, str]:
    """Return (plain token to give the client, hash to store)."""
    plain = secrets.token_urlsafe(32)
    return plain, hash_refresh_token(plain)


def hash_refresh_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()
