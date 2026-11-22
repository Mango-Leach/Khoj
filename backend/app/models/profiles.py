from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.auth import Lang
from app.services.catalog import district_ids

State = Literal["Maharashtra"]
TeacherRole = Literal["teacher", "mentor", "facilitator", "expert"]

# grade: 9 to 12 are Class 9 to 12; 13 is college (studying); 14 is a graduate.
GRADES = range(9, 15)
MINOR_AGE = 18

_SKILL_TAG = re.compile(r"^[a-z0-9_]{2,40}$")


def age_band(age: int) -> str:
    """The spec's three bands. Guardian consent and placement filters key off these."""
    if age < 16:
        return "14-16"
    if age < 18:
        return "16-18"
    return "18+"


def _check_district(value: str) -> str:
    if value not in district_ids():
        raise ValueError("unknown district")
    return value


class StudentProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    age: int = Field(ge=10, le=40)  # sanity bounds; the target range is about 14 to 24
    grade: int
    state: State = "Maharashtra"
    district: str
    block: str = Field(min_length=1, max_length=80)  # taluka, free text until a verified list exists
    guardian_consent: bool = False

    @field_validator("name", "block")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("grade")
    @classmethod
    def _grade(cls, v: int) -> int:
        if v not in GRADES:
            raise ValueError("grade must be 9 to 14")
        return v

    @field_validator("district")
    @classmethod
    def _district(cls, v: str) -> str:
        return _check_district(v)

    @model_validator(mode="after")
    def _consent_for_minors(self) -> "StudentProfileIn":
        if self.age < MINOR_AGE and not self.guardian_consent:
            raise ValueError("guardian_consent_required")
        return self


class StudentProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    age: int | None = Field(default=None, ge=10, le=40)
    grade: int | None = None
    district: str | None = None
    block: str | None = Field(default=None, min_length=1, max_length=80)
    guardian_consent: bool | None = None


class TeacherProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    roles: list[TeacherRole] = Field(min_length=1, max_length=4)
    skills: list[str] = Field(default_factory=list, max_length=20)  # unverified claims until assessed
    languages: list[Lang] = Field(min_length=1, max_length=3)
    state: State = "Maharashtra"
    district: str
    block: str = Field(min_length=1, max_length=80)
    weekly_hours: int = Field(ge=1, le=60)

    @field_validator("name", "block")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("district")
    @classmethod
    def _district(cls, v: str) -> str:
        return _check_district(v)

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for tag in v:
            tag = tag.strip().lower().replace(" ", "_")
            if not _SKILL_TAG.match(tag):
                raise ValueError("skill tags are 2 to 40 letters, digits or underscores")
            if tag not in out:
                out.append(tag)
        return out

    @field_validator("roles", "languages")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(v))


class TeacherProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    roles: list[TeacherRole] | None = Field(default=None, min_length=1, max_length=4)
    skills: list[str] | None = Field(default=None, max_length=20)
    languages: list[Lang] | None = Field(default=None, min_length=1, max_length=3)
    district: str | None = None
    block: str | None = Field(default=None, min_length=1, max_length=80)
    weekly_hours: int | None = Field(default=None, ge=1, le=60)
