from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.schemes import SchemeFacts


class ApplicationPatch(BaseModel):
    """The learner's own next step. `interested` and `mentor_assisted` are set by other calls."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["applied", "confirmed", "withdrawn"]


class OpportunityCheckIn(BaseModel):
    """Answers for this check only. They are not stored."""

    model_config = ConfigDict(extra="forbid")

    facts: SchemeFacts = SchemeFacts()
