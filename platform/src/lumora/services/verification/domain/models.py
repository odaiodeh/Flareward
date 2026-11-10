"""Opt-in evidence and acceptance contracts, independent of any candidate protocol."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from lumora.services.artifacts.domain.models import (
    ArtifactMediaType,
    BlobArtifactRef,
    ContentIdentity,
)
from lumora.services.identity.domain import Identity

type VerificationId = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
type CheckId = Annotated[str, Field(min_length=1, max_length=128)]
type VerifierId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]


class VerificationSubject(BaseModel):
    """A check's explicit immutable input; ordinary operation outputs need no wrapper."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    kind: str = Field(min_length=1, max_length=128)
    identity: dict[str, JsonValue] = Field(min_length=1)

    def canonical(self) -> bytes:
        return json.dumps(
            [self.kind, self.identity],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()

    @model_validator(mode="after")
    def bounded_identity(self) -> Self:
        try:
            if len(self.canonical()) > 65_536:
                raise ValueError("Verification subject exceeds its byte limit")
        except RecursionError, UnicodeError:
            raise ValueError("Verification subject is not portable JSON") from None
        return self

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


class CheckRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check: CheckId
    verifiers: frozenset[VerifierId] = Field(min_length=1, max_length=32)
    requires_reports: bool = False


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    plan_id: VerificationId
    owner: Identity
    root_execution_id: str | None = Field(default=None, min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=256)
    subject: VerificationSubject
    policy: str = Field(min_length=1, max_length=128)
    requirements: tuple[CheckRequirement, ...] = Field(min_length=1, max_length=32)
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        checks = [requirement.check for requirement in self.requirements]
        if len(set(checks)) != len(checks) or self.expires_at <= self.created_at:
            raise ValueError("Verification plan requires unique checks and a future deadline")
        return self


class CheckVerdict(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class CheckReportSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    external_id: str = Field(min_length=1, max_length=256)
    name: str = Field(min_length=1, max_length=255)
    identity: ContentIdentity
    media_type: ArtifactMediaType = "application/octet-stream"


class CheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    source: CheckReportSource
    content: BlobArtifactRef

    @model_validator(mode="after")
    def identical_content(self) -> Self:
        if (
            self.content.sha256 != self.source.identity.sha256
            or self.content.size_bytes != self.source.identity.size_bytes
        ):
            raise ValueError("Check report must preserve its source content identity")
        return self


class CheckEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    check: CheckId
    verifier: VerifierId
    subject_fingerprint: VerificationId
    run_id: str = Field(min_length=1, max_length=256)
    verdict: CheckVerdict
    recorded_at: AwareDatetime
    configuration_digest: VerificationId | None = None
    reports: tuple[CheckReport, ...] = Field(default=(), max_length=16)


class VerificationOutcome(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class VerificationState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    plan: VerificationPlan
    evidence: tuple[CheckEvidence, ...] = Field(default=(), max_length=32)
    cancelled: bool = False
    revision: int = Field(default=0, ge=0)

    @property
    def evidence_outcome(self) -> VerificationOutcome | None:
        """Return the outcome fixed by recorded state, independent of the clock."""
        verdicts = {receipt.verdict for receipt in self.evidence}
        if self.cancelled:
            return VerificationOutcome.CANCELLED
        if CheckVerdict.FAILED in verdicts:
            return VerificationOutcome.REJECTED
        if CheckVerdict.ERROR in verdicts:
            return VerificationOutcome.ERROR
        if len(self.evidence) == len(self.plan.requirements):
            return VerificationOutcome.ACCEPTED
        return None

    @model_validator(mode="after")
    def evidence_matches_plan(self) -> Self:
        requirements = {requirement.check: requirement for requirement in self.plan.requirements}
        fingerprint = self.plan.subject.fingerprint
        seen: set[str] = set()
        for receipt in self.evidence:
            expected = requirements.get(receipt.check)
            if (
                receipt.check in seen
                or expected is None
                or receipt.verifier not in expected.verifiers
                or receipt.subject_fingerprint != fingerprint
                or (expected.requires_reports and not receipt.reports)
                or not self.plan.created_at <= receipt.recorded_at < self.plan.expires_at
            ):
                raise ValueError("Evidence does not match its verification plan")
            seen.add(receipt.check)
        return self
