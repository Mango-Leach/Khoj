"""OTP login, token rotation and session handling, end to end through the HTTP API."""
import json

from app.config import Settings, get_settings
from app.main import app
from tests.conftest import OTHER_PHONE, OTP, PHONE, STUDENT, bearer, sign_in

API = "/api/v1"


async def request_otp(client, phone=PHONE):
    return await client.post(f"{API}/auth/otp/request", json={"phone": phone})


async def verify(client, otp=OTP, phone=PHONE):
    return await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "otp": otp})


# --- login ----------------------------------------------------------------


async def test_login_creates_a_user_and_returns_tokens(client, clock):
    tokens = await sign_in(client, clock)
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] == 900
    assert tokens["user"]["roles"] == [] and tokens["user"]["profile"] is None
    assert "has_pin" not in tokens["user"]


async def test_same_phone_always_maps_to_the_same_user(client, clock):
    first = await sign_in(client, clock)
    second = await sign_in(client, clock)
    assert first["user"]["id"] == second["user"]["id"]


async def test_different_phones_are_different_users(client, clock):
    a = await sign_in(client, clock, PHONE)
    b = await sign_in(client, clock, OTHER_PHONE)
    assert a["user"]["id"] != b["user"]["id"]


async def test_formatted_numbers_reach_the_same_account(client, clock):
    a = await sign_in(client, clock, "9876543210")
    b = await sign_in(client, clock, "+91 98765 43210")
    assert a["user"]["id"] == b["user"]["id"]


async def test_invalid_phone_is_rejected(client):
    r = await request_otp(client, "1234567890")
    assert r.status_code == 422 and r.json()["code"] == "invalid_phone"


async def test_number_outside_the_demo_list_is_refused(client):
    r = await request_otp(client, "9000000001")
    assert r.status_code == 403 and r.json()["code"] == "number_not_allowed"


async def test_wildcard_allows_any_number_for_local_dev(client, settings):
    app.dependency_overrides[get_settings] = lambda: Settings(**{**settings.model_dump(), "demo_phones": "*"})
    assert (await request_otp(client, "9000000001")).status_code == 200


async def test_any_number_can_sign_in_with_the_demo_code_when_the_switch_is_on_and_listed_numbers_still_work(client, settings):
    app.dependency_overrides[get_settings] = lambda: Settings(**{**settings.model_dump(), "demo_allow_any_number": True})
    r = await request_otp(client, "9000000001")
    assert r.status_code == 200
    ok = await client.post("/api/v1/auth/otp/verify", json={"phone": "9000000001", "otp": settings.demo_otp})
    assert ok.status_code == 200 and ok.json()["access_token"]
    assert (await request_otp(client, settings.demo_phones.split(",")[0])).status_code == 200  # a listed number is unaffected
    wrong = await client.post("/api/v1/auth/otp/verify", json={"phone": "9000000001", "otp": "000000"})
    assert wrong.status_code == 401  # it is still a code check, not an open door


async def test_nobody_becomes_admin_while_any_number_may_sign_in(client, settings):
    both = Settings(**{**settings.model_dump(), "demo_allow_any_number": True, "admin_phones": "9000000002"})
    app.dependency_overrides[get_settings] = lambda: both
    assert (await request_otp(client, "9000000002")).status_code == 200
    ok = await client.post("/api/v1/auth/otp/verify", json={"phone": "9000000002", "otp": settings.demo_otp})
    assert ok.status_code == 200 and "admin" not in ok.json()["user"]["roles"]
    # with the switch off, the same setting still grants admin to that number
    off = Settings(**{**settings.model_dump(), "demo_phones": "9000000003", "admin_phones": "9000000003"})
    app.dependency_overrides[get_settings] = lambda: off
    assert (await request_otp(client, "9000000003")).status_code == 200
    ok = await client.post("/api/v1/auth/otp/verify", json={"phone": "9000000003", "otp": settings.demo_otp})
    assert "admin" in ok.json()["user"]["roles"]


async def test_sms_login_is_not_available_outside_demo_mode(client, settings):
    app.dependency_overrides[get_settings] = lambda: Settings(**{**settings.model_dump(), "demo_mode": False})
    r = await request_otp(client)
    assert r.status_code == 501 and r.json()["code"] == "sms_not_configured"


# --- OTP rules ------------------------------------------------------------


async def test_resend_cooldown(client, clock):
    assert (await request_otp(client)).status_code == 200
    r = await request_otp(client)
    assert r.status_code == 429 and r.json()["code"] == "otp_cooldown" and r.json()["retry_after"] >= 1
    clock.advance(31)
    assert (await request_otp(client)).status_code == 200


async def test_per_number_request_limit(client, clock):
    for _ in range(5):
        assert (await request_otp(client)).status_code == 200
        clock.advance(31)
    r = await request_otp(client)
    assert r.status_code == 429 and r.json()["code"] == "too_many_requests"
    clock.advance(600)  # the 10-minute window passes
    assert (await request_otp(client)).status_code == 200


async def test_wrong_code_is_rejected(client):
    await request_otp(client)
    r = await verify(client, "000000")
    assert r.status_code == 401 and r.json()["code"] == "invalid_otp"


async def test_three_wrong_codes_lock_that_code_even_for_the_right_answer(client):
    await request_otp(client)
    for _ in range(3):
        assert (await verify(client, "000000")).status_code == 401
    r = await verify(client, OTP)
    assert r.status_code == 429 and r.json()["code"] == "otp_attempts_exceeded"


async def test_a_code_works_only_once(client):
    await request_otp(client)
    assert (await verify(client)).status_code == 200
    assert (await verify(client)).status_code == 401


async def test_code_expires_after_five_minutes(client, clock):
    await request_otp(client)
    clock.advance(301)
    assert (await verify(client)).status_code == 401


async def test_verify_without_a_request_fails_the_same_way(client):
    r = await verify(client)
    assert r.status_code == 401 and r.json()["code"] == "invalid_otp"


async def test_malformed_otp_is_a_validation_error_that_does_not_echo_input(client):
    r = await client.post(f"{API}/auth/otp/verify", json={"phone": PHONE, "otp": "12ab56"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert PHONE not in r.text and "12ab56" not in r.text


# --- tokens ---------------------------------------------------------------


async def test_refresh_rotates_the_token(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["refresh_token"] != tokens["refresh_token"]
    assert r.json()["user"]["id"] == tokens["user"]["id"]


async def test_replaying_a_used_refresh_token_ends_the_whole_session_family(client, clock):
    tokens = await sign_in(client, clock)
    rotated = (await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).json()
    replay = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401 and replay.json()["code"] == "invalid_refresh_token"
    # the legitimate newer token is revoked too, because the family is now suspect
    again = await client.post(f"{API}/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert again.status_code == 401


async def test_refresh_token_expires_after_thirty_days(client, clock):
    tokens = await sign_in(client, clock)
    clock.advance(31 * 24 * 3600)
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_unknown_refresh_token_is_rejected(client):
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": "x" * 43})
    assert r.status_code == 401


async def test_logout_revokes_the_refresh_token(client, clock):
    tokens = await sign_in(client, clock)
    assert (await client.post(f"{API}/auth/logout", json={"refresh_token": tokens["refresh_token"]})).status_code == 204
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_secrets_are_stored_hashed_and_the_phone_is_not_stored_in_clear(client, clock, db):
    tokens = await sign_in(client, clock)
    docs = []
    for name in ("users", "otp_requests", "refresh_tokens"):
        docs += [d async for d in db[name].find({})]
    stored = json.dumps(docs, default=str)
    assert tokens["refresh_token"] not in stored
    assert OTP not in stored.replace("otp_hash", "")  # the demo code itself is never stored
    assert PHONE not in stored and "+91" + PHONE not in stored


# --- sessions and /me -----------------------------------------------------


async def test_me_requires_a_session(client):
    r = await client.get(f"{API}/me")
    assert r.status_code == 401 and r.json()["code"] == "not_authenticated"
    assert set(r.json()) >= {"code", "message", "hint"}


async def test_me_with_a_session(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.get(f"{API}/me", headers=bearer(tokens))
    assert r.status_code == 200 and r.json()["id"] == tokens["user"]["id"]


async def test_a_tampered_token_is_rejected(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.get(f"{API}/me", headers={"Authorization": f"Bearer {tokens['access_token'][:-4]}abcd"})
    assert r.status_code == 401 and r.json()["code"] == "invalid_token"


async def test_expired_access_token(client, clock, settings):
    tokens = await sign_in(client, clock)
    app.dependency_overrides[get_settings] = lambda: Settings(**{**settings.model_dump(), "access_token_minutes": 15})
    # PyJWT checks `exp` against the real clock, so expiry is exercised with a past-dated token
    from app import security

    expired, _ = security.create_access_token(Settings(**{**settings.model_dump(), "access_token_minutes": -1}), tokens["user"]["id"], [])
    r = await client.get(f"{API}/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["code"] == "token_expired"


async def test_preferences_can_be_updated(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.patch(
        f"{API}/me/preferences",
        headers=bearer(tokens),
        json={"language": "mr", "channels": {"in_app": True, "push": True, "sms": False, "whatsapp": False}, "quiet_hours": {"start": "22:00", "end": "06:30"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "mr" and body["preferences"]["channels"]["push"] is True
    assert body["preferences"]["quiet_hours"] == {"start": "22:00", "end": "06:30"}


async def test_unsupported_language_is_rejected(client, clock):
    tokens = await sign_in(client, clock)
    r = await client.patch(f"{API}/me/preferences", headers=bearer(tokens), json={"language": "fr"})
    assert r.status_code == 422


async def test_roles_are_read_from_the_database_not_the_token(client, clock):
    tokens = await sign_in(client, clock)
    assert (await client.get(f"{API}/students/me", headers=bearer(tokens))).status_code == 403
    await client.post(f"{API}/students/profile", headers=bearer(tokens), json=STUDENT)
    # same access token, issued before the role existed
    r = await client.get(f"{API}/me", headers=bearer(tokens))
    assert r.json()["roles"] == ["student"] and r.json()["profile"] == "student"
