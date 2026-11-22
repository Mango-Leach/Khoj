"""One error shape for the whole API: { code, message, hint } (CLAUDE.md section 13).

Clients translate by `code`. `hint` is English for now; server-side translation of hints
is not built yet.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, hint: str = "", **extra: Any) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.hint = hint
        self.extra = extra

    def body(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "hint": self.hint, **self.extra}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.body())


def validation_payload(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the 422 body. Pydantic echoes the submitted value in `input`, which can be a
    phone number or OTP, so it is dropped. Only where and why a field failed is returned."""
    fields = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "reason": e["type"], "message": e["msg"]} for e in errors
    ]
    consent = any("guardian_consent_required" in e["msg"] for e in errors)
    return jsonable_encoder(
        {
            "code": "guardian_consent_required" if consent else "validation_error",
            "message": "A guardian's consent is needed for under-18s." if consent else "Some fields are not valid.",
            "hint": "Ask a parent or guardian to agree." if consent else "Check the highlighted fields.",
            "fields": fields,
        }
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=validation_payload(list(exc.errors())))
