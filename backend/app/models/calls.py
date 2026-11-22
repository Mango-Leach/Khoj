from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_PHONE = re.compile(r"^[6-9]\d{9}$")


def checked_contact(kind: str, contact: str) -> str:
    """A web link (https only) or the host's own 10 digit mobile number. Anything else is refused."""
    if kind == "link":
        if not contact.startswith("https://") or " " in contact or len(contact) < 12:
            raise ValueError("a link must start with https://")
        return contact
    digits = re.sub(r"[\s-]", "", contact)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not _PHONE.match(digits):
        raise ValueError("a phone number has 10 digits")
    return digits


class CallSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offers_calls: bool


class SlotIn(BaseModel):
    """One 30 or 45 minute time a mentor offers. The contact is where the learner reaches them once the slot is booked."""

    model_config = ConfigDict(extra="forbid")
    career_id: str = Field(min_length=2, max_length=60)
    starts_at: datetime
    minutes: Literal[30, 45]
    contact_kind: Literal["link", "phone"]
    contact: str = Field(min_length=3, max_length=200)

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("starts_at needs a time zone")
        return v

    @field_validator("contact")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    def checked_contact(self) -> str:
        return checked_contact(self.contact_kind, self.contact)


class BookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agreed: bool = False  # the short code of conduct was read
    guardian_near: bool = False  # for a learner under 18: a guardian or facilitator will be nearby during the call


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    took_place: bool
    rating: int | None = Field(default=None, ge=1, le=5)
