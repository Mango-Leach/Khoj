from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "hi", "mr"]


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class OtpRequestOut(BaseModel):
    expires_in: int
    resend_after: int


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    otp: str = Field(pattern=r"^\d{6}$")


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class NotificationChannels(BaseModel):
    in_app: bool = True
    push: bool = False
    sms: bool = False
    whatsapp: bool = False


class QuietHours(BaseModel):
    start: str = Field(default="21:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Preferences(BaseModel):
    channels: NotificationChannels = NotificationChannels()
    quiet_hours: QuietHours = QuietHours()


class PreferencesPatch(BaseModel):
    language: Lang | None = None
    channels: NotificationChannels | None = None
    quiet_hours: QuietHours | None = None


class UserOut(BaseModel):
    id: str
    roles: list[str]
    language: Lang
    profile: Literal["student", "teacher"] | None
    preferences: Preferences


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut
