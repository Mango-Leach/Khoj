from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Lang = Literal["en", "hi", "mr"]


def _clean(v: str) -> str:
    return " ".join(v.split()) if "\n" not in v else "\n".join(" ".join(line.split()) for line in v.strip().splitlines()).strip()


class AssignmentIn(BaseModel):
    """A mentor writing an assignment themselves. The text is in one language; learners in another see it as written."""

    model_config = ConfigDict(extra="forbid")
    lang: Lang = "en"
    title: str = Field(min_length=3, max_length=100)
    instructions: str = Field(min_length=10, max_length=900)
    criteria: list[str] = Field(min_length=3, max_length=5)

    @field_validator("title", "instructions")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean(v)

    @field_validator("criteria")
    @classmethod
    def _criteria(cls, v: list[str]) -> list[str]:
        out = [_clean(c) for c in v]
        if any(len(c) < 3 or len(c) > 140 for c in out):
            raise ValueError("each criterion is 3 to 140 characters")
        return out


class AssignmentPatch(BaseModel):
    """Edit a draft, or approve or retire an assignment. Content fields apply to the draft only."""

    model_config = ConfigDict(extra="forbid")
    lang: Lang = "en"
    title: str | None = Field(default=None, min_length=3, max_length=100)
    instructions: str | None = Field(default=None, min_length=10, max_length=900)
    criteria: list[str] | None = Field(default=None, min_length=3, max_length=5)
    status: Literal["approved", "retired"] | None = None

    @field_validator("title", "instructions")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return _clean(v) if v is not None else None

    @field_validator("criteria")
    @classmethod
    def _criteria(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = [_clean(c) for c in v]
        if any(len(c) < 3 or len(c) > 140 for c in out):
            raise ValueError("each criterion is 3 to 140 characters")
        return out


class SubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=2000)
    via: Literal["typed", "voice"] = "typed"

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class AckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Literal["yes", "no"]


class ReviewIn(BaseModel):
    """One explicit score per criterion (1 to 4). There is no way to approve without scoring each one."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "return"]
    scores: dict[str, int]
    feedback: str = Field(default="", max_length=1200)

    @field_validator("scores")
    @classmethod
    def _range(cls, v: dict[str, int]) -> dict[str, int]:
        if any(s < 1 or s > 4 for s in v.values()):
            raise ValueError("scores are 1 to 4")
        return v

    @field_validator("feedback")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()
