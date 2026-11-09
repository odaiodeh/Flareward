"""The exact work and accepted evidence presented for an Engineering decision."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flareward.services.verification.domain.models import VerificationOutcome, VerificationSubject
from flareward.services.verification.models import VerificationView


class EngineeringReviewSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    kind: Literal["engineering-review@2"] = "engineering-review@2"
    completion: str = Field(min_length=1, max_length=128)
    candidate: VerificationSubject
    verification: VerificationView

    @model_validator(mode="after")
    def accepted_candidate(self) -> Self:
        if self.verification.state.plan.subject.fingerprint != self.candidate.fingerprint:
            raise ValueError("Engineering review requires evidence for the exact candidate")
        if self.verification.outcome != VerificationOutcome.ACCEPTED:
            raise ValueError("Engineering review requires accepted verification evidence")
        return self
