from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CredentialKind = Literal["certificate", "work_sample", "experience", "reference"]


class CredentialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: CredentialKind
    title: str = Field(min_length=2, max_length=100)
    note: str = Field(default="", max_length=500)

    @field_validator("title", "note")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class TestSubmitIn(BaseModel):
    """One score per sample, 1 to 4. The area's items are checked in the service."""

    model_config = ConfigDict(extra="forbid")
    scores: dict[str, int]

    @field_validator("scores")
    @classmethod
    def _range(cls, v: dict[str, int]) -> dict[str, int]:
        if any(s < 1 or s > 4 for s in v.values()):
            raise ValueError("scores are 1 to 4")
        return v


class EvidenceDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=300)


class MentorRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    teacher_id: str = Field(min_length=8, max_length=64)
