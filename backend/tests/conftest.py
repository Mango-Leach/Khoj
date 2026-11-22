"""Shared fixtures: an in-memory MongoDB, a controllable clock, and an HTTP client."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app import timeutil
from app.config import Settings, get_settings
from app.deps import get_db
from app.indexes import ensure_indexes
from app.main import app

PHONE = "9876543210"
OTHER_PHONE = "9123456789"
OTP = "123456"


class Clock:
    def __init__(self) -> None:
        # Far in the future on purpose. The in-memory database applies TTL expiry against the
        # real clock, so a frozen date the real clock can reach would silently delete test
        # data (one-time codes, refresh tokens) partway through the day.
        self.now = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(timeutil, "utcnow", lambda: c.now)
    return c


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        demo_mode=True,
        demo_phones=f"{PHONE},{OTHER_PHONE}",
        jwt_secret="test-secret-0123456789-0123456789-xyz",
    )


@pytest.fixture
async def db():
    database = AsyncMongoMockClient()["khoj_test"]
    await ensure_indexes(database)
    return database


@pytest.fixture
async def client(settings, db, clock):
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def sign_in(client: AsyncClient, clock: Clock, phone: str = PHONE, otp: str = OTP) -> dict:
    """Request and verify an OTP. Advances the clock past the resend cooldown first."""
    clock.advance(60)
    r = await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
    assert r.status_code == 200, r.text
    return r.json()


def bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


STUDENT = {"name": "Priya", "age": 16, "grade": 10, "district": "pune", "block": "Haveli", "guardian_consent": True}
TEACHER = {
    "name": "Mrs. Patil",
    "roles": ["teacher", "mentor"],
    "skills": ["Sewing Machine", "tailoring"],
    "languages": ["mr", "hi"],
    "district": "nashik",
    "block": "Igatpuri",
    "weekly_hours": 6,
}
