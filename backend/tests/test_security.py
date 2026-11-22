import pytest

from app import security, timeutil
from app.config import Settings
from app.errors import ApiError


def s(**kw) -> Settings:
    return Settings(_env_file=None, jwt_secret="test-secret-0123456789-0123456789-xyz", **kw)


@pytest.mark.parametrize(
    "raw",
    ["9876543210", "+91 98765 43210", "09876543210", "919876543210", "+91-98765-43210", " (98765) 43210 "],
)
def test_phone_formats_normalise_to_one_form(raw):
    assert security.normalize_phone(raw) == "+919876543210"


@pytest.mark.parametrize("raw", ["", "12345", "1234567890", "5876543210", "98765432101", "abcdefghij", "+1 555 123 4567"])
def test_invalid_phones_are_rejected(raw):
    assert security.normalize_phone(raw) is None


def test_phone_hash_is_stable_and_keyed():
    a = security.phone_hash(s(), "+919876543210")
    assert a == security.phone_hash(s(), "+919876543210")
    assert a != security.phone_hash(Settings(_env_file=None, jwt_secret="other-secret-0123456789-0123456789-abc"), "+919876543210")
    assert "9876543210" not in a


def test_phone_encryption_round_trips_and_hides_the_number():
    token = security.encrypt_phone(s(), "+919876543210")
    assert "9876543210" not in token
    assert security.decrypt_phone(s(), token) == "+919876543210"
    assert security.decrypt_phone(Settings(_env_file=None, jwt_secret="other-secret-0123456789-0123456789-abc"), token) is None


def test_mask_phone_hides_the_middle():
    assert security.mask_phone("+919876543210") == "+91XXXXX210"


def test_access_token_round_trip():
    settings = s()
    token, ttl = security.create_access_token(settings, "user-1", ["student"])
    assert ttl == 15 * 60
    claims = security.decode_access_token(settings, token)
    assert claims["sub"] == "user-1" and claims["typ"] == "access"


def test_tampered_or_foreign_tokens_are_rejected():
    settings = s()
    token, _ = security.create_access_token(settings, "user-1", [])
    with pytest.raises(ApiError) as e:
        security.decode_access_token(settings, token[:-3] + "abc")
    assert e.value.code == "invalid_token"
    with pytest.raises(ApiError):
        security.decode_access_token(Settings(_env_file=None, jwt_secret="another-secret-0123456789-0123456789-abc"), token)


def test_expired_token_has_its_own_code():
    settings = s(access_token_minutes=-1)
    token, _ = security.create_access_token(settings, "user-1", [])
    with pytest.raises(ApiError) as e:
        security.decode_access_token(settings, token)
    assert e.value.code == "token_expired"


def test_refresh_tokens_are_random_and_stored_hashed():
    plain, hashed = security.new_refresh_token()
    plain2, _ = security.new_refresh_token()
    assert plain != plain2
    assert hashed == security.hash_refresh_token(plain)
    assert plain not in hashed


def test_placeholder_secret_is_refused_outside_dev():
    security.assert_secrets_ok(Settings(_env_file=None, app_env="dev", jwt_secret="change-me"))
    with pytest.raises(RuntimeError):
        security.assert_secrets_ok(Settings(_env_file=None, app_env="prod", jwt_secret="change-me"))
    with pytest.raises(RuntimeError):  # too short to be a real secret
        security.assert_secrets_ok(Settings(_env_file=None, app_env="prod", jwt_secret="short"))
    security.assert_secrets_ok(Settings(_env_file=None, app_env="prod", jwt_secret="x" * 40))


def test_ensure_aware_treats_naive_as_utc():
    from datetime import datetime

    assert timeutil.ensure_aware(datetime(2026, 1, 1)).utcoffset().total_seconds() == 0
