from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.calls import checked_contact


class MyCardIn(BaseModel):
    """Switch the learner's card on or off, and set the one way connections can reach them outside KHOJ."""

    model_config = ConfigDict(extra="forbid")
    visible: bool
    reach_kind: Literal["phone", "link"] = "phone"
    reach: str = Field(default="", max_length=200)
    agreed: bool = False  # understands KHOJ cannot see or protect what happens off the platform

    @field_validator("reach")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    def checked_reach(self) -> str:
        return checked_contact(self.reach_kind, self.reach)


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["pressure", "unsafe", "spam", "other"]
