"""Application requests, operator policy and authenticated verifier authority."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mas.core.identity import Identity
from mas.domain.verification import (
    CheckId,
    CheckReport,
    CheckRequirement,
    CheckVerdict,
    VerificationId,
    VerificationOutcome,
    VerificationState,
    VerificationSubject,
    VerifierId,
)


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owners: tuple[Identity, ...] = Field(min_length=1, max_length=128)
    subject_kind: str = Field(min_length=1, max_length=128)
    requirements: tuple[CheckRequirement, ...] = Field(min_length=1, max_length=32)
    timeout_seconds: int = Field(default=3600, ge=60, le=2_592_000)

    @model_validator(mode="after")
    def unique_checks(self) -> Self:
        checks = [requirement.check for requirement in self.requirements]
        if len(set(checks)) != len(checks):
            raise ValueError("Verification policy requires unique checks")
        return self


class VerificationAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    verifier: VerifierId
    owners: tuple[Identity, ...] = Field(min_length=1, max_length=128)


class StartVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=256)
    subject: VerificationSubject
    policy: str = Field(min_length=1, max_length=128)


class SubmitCheckEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    plan_id: VerificationId
    subject: VerificationSubject
    check: CheckId
    run_id: str = Field(min_length=1, max_length=256)
    verdict: CheckVerdict
    configuration_digest: VerificationId | None = None
    reports: tuple[CheckReport, ...] = Field(default=(), max_length=16)


class VerificationView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state: VerificationState
    outcome: VerificationOutcome

    @model_validator(mode="after")
    def outcome_matches_evidence(self) -> Self:
        fixed = self.state.evidence_outcome
        if (fixed is not None and self.outcome != fixed) or (
            fixed is None
            and self.outcome not in {VerificationOutcome.PENDING, VerificationOutcome.EXPIRED}
        ):
            raise ValueError("Verification outcome does not match recorded evidence")
        return self
