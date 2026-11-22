import { describe, expect, it } from "vitest";
import { ApiFailure } from "./api";
import { errorKey } from "./errors";
import en from "../i18n/en.json";

describe("errorKey", () => {
  it("maps known server codes to their message", () => {
    expect(errorKey(new ApiFailure(401, "invalid_otp"))).toBe("err.invalid_otp");
    expect(errorKey(new ApiFailure(409, "role_conflict"))).toBe("err.role_conflict");
    expect(errorKey(new ApiFailure(422, "guardian_consent_required"))).toBe("err.guardian_consent_required");
  });

  it("maps a lost connection to the network message", () => {
    expect(errorKey(new ApiFailure(0, "network"))).toBe("err.network");
  });

  it("falls back to a generic message for unknown codes and non-API errors", () => {
    expect(errorKey(new ApiFailure(500, "something_new"))).toBe("err.generic");
    expect(errorKey(new Error("boom"))).toBe("err.generic");
  });

  it("has a message for every error code the backend can raise at sign-in and profile time", () => {
    const codes = [
      "invalid_phone", "number_not_allowed", "sms_not_configured", "otp_cooldown", "too_many_requests",
      "invalid_otp", "otp_attempts_exceeded", "role_conflict", "profile_exists",
      "guardian_consent_required", "validation_error", "invalid_refresh_token", "db_unavailable",
    ];
    for (const code of codes) expect(`err.${code}` in en, code).toBe(true);
  });
});
