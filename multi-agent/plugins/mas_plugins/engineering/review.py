"""The exact work and accepted evidence presented for an Engineering decision."""

from typing import Literal, Self

from mas.application.verification.models import VerificationView
from mas.domain.verification import VerificationOutcome, VerificationSubject
from pydantic import BaseModel, ConfigDict, model_validator


class EngineeringReviewSubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    kind: Literal["engineering-review@1"] = "engineering-review@1"
    candidate: VerificationSubject
    verification: VerificationView

    @model_validator(mode="after")
    def accepted_candidate(self) -> Self:
        if self.verification.state.plan.subject.fingerprint != self.candidate.fingerprint:
            raise ValueError("Engineering review requires evidence for the exact candidate")
        if self.verification.outcome != VerificationOutcome.ACCEPTED:
            raise ValueError("Engineering review requires accepted verification evidence")
        return self
