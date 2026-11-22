from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.auth import Lang

AnswerSource = Literal["typed", "browser_asr", "gnani", "bhashini", "tap"]
Budget = Literal["none", "low", "medium", "unknown"]
MoveAway = Literal["yes", "no", "unknown"]
EarnedBefore = Literal["earned", "helped", "no", "unknown"]
Priority = Literal["earn_soon", "earn_more", "near_home", "govt_job", "own_business", "unknown"]

MAX_CATEGORIES = 3


class SessionCreate(BaseModel):
    category_ids: list[str] = Field(default_factory=list, max_length=MAX_CATEGORIES)
    not_sure: bool = False
    language: Lang = "en"

    @field_validator("category_ids")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class ConfirmIn(BaseModel):
    """One confirmed answer. The learner has already seen the transcript and agreed to it."""

    question_id: str = Field(min_length=1, max_length=40)
    transcript: str = Field(default="", max_length=2000)
    choice_id: str | None = Field(default=None, max_length=40)
    source: AnswerSource = "typed"
    language: Lang = "en"  # the language the learner spoke or typed in


class Constraints(BaseModel):
    budget: Budget = "unknown"
    can_move_away: MoveAway = "unknown"
    hours_per_week: int | None = Field(default=None, ge=0, le=80)
    earned_before: EarnedBefore = "unknown"
    priority: Priority = "unknown"


class LLMExtraction(BaseModel):
    """What the model is asked to return. Deliberately small, so a 3B local model can fill it."""

    model_config = ConfigDict(extra="ignore")

    skills: list[str] = Field(default_factory=list)
    other_skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    goal: str | None = None


class Translation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    english: str = Field(min_length=1, max_length=2000)


class Extracted(BaseModel):
    """The validated profile stored on the session. Skills are ids from the controlled vocabulary."""

    skills: list[str] = Field(default_factory=list, max_length=8)
    # skills the learner added themselves on the review screen (a subset of `skills`)
    learner_added: list[str] = Field(default_factory=list, max_length=8)
    other_skills: list[str] = Field(default_factory=list, max_length=5)
    interests: list[str] = Field(default_factory=list, max_length=6)
    goal: str | None = Field(default=None, max_length=160)
    constraints: Constraints = Constraints()


class AcceptIn(BaseModel):
    """The learner's corrections on the review screen. Constraints are not editable here."""

    skills: list[str] = Field(default_factory=list, max_length=8)
    other_skills: list[str] = Field(default_factory=list, max_length=5)
    interests: list[str] = Field(default_factory=list, max_length=6)
    goal: str | None = Field(default=None, max_length=160)
