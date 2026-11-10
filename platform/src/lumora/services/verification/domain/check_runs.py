"""Durable check dispatch identities and observations, without provider wire types."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.models import (
    CheckEvidence,
    CheckId,
    CheckReport,
    CheckReportSource,
    CheckVerdict,
    VerificationId,
    VerificationPlan,
    VerifierId,
)


class CheckRunStatus(StrEnum):
    READY = "ready"
    UNCERTAIN = "uncertain"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"


class CheckJobState(StrEnum):
    ACTIVE = "active"
    RETIRING = "retiring"
    CLOSED = "closed"


class CheckRunObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    external_id: str = Field(min_length=1, max_length=256)
    status: CheckRunStatus
    verdict: CheckVerdict | None = None

    @model_validator(mode="after")
    def observed_status(self) -> Self:
        if self.status not in {
            CheckRunStatus.QUEUED,
            CheckRunStatus.RUNNING,
            CheckRunStatus.COMPLETED,
        } or (self.status == CheckRunStatus.COMPLETED) != (self.verdict is not None):
            raise ValueError("Check observation requires a provider run and a terminal verdict")
        return self


class CheckRunResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=128)
    external_id: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1000)
    issued_by: Identity
    recorded_at: AwareDatetime

    @model_validator(mode="after")
    def human_issuer(self) -> Self:
        if not self.issued_by.is_user or not self.issued_by.id:
            raise ValueError("Check resolution requires an authenticated human")
        return self


class CheckRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    intent_id: VerificationId
    plan: VerificationPlan
    check: CheckId
    runner: str = Field(min_length=1, max_length=128)
    verifier: VerifierId
    configuration_digest: VerificationId
    created_at: AwareDatetime
    status: CheckRunStatus = CheckRunStatus.READY
    observation: CheckRunObservation | None = None
    evidence_recorded: bool = False
    report_sources: tuple[CheckReportSource, ...] | None = Field(default=None, max_length=16)
    reports: tuple[CheckReport, ...] = Field(default=(), max_length=16)
    reports_collected: bool = False
    resolution: CheckRunResolution | None = None
    revision: int = Field(default=0, ge=0)
    job_state: CheckJobState | None = None

    def matches_receipt(self, receipt: CheckEvidence) -> bool:
        observation = self.observation
        return (
            self.reports_collected
            and observation is not None
            and observation.status == CheckRunStatus.COMPLETED
            and receipt.check == self.check
            and receipt.verifier == self.verifier
            and receipt.run_id == observation.external_id
            and receipt.verdict == observation.verdict
            and receipt.subject_fingerprint == self.plan.subject.fingerprint
            and receipt.configuration_digest == self.configuration_digest
            and receipt.reports == self.reports
        )

    @model_validator(mode="after")
    def consistent_run(self) -> Self:
        requirement = next(
            (item for item in self.plan.requirements if item.check == self.check), None
        )
        if requirement is None or self.verifier not in requirement.verifiers:
            raise ValueError("Check run is not authorized by its verification plan")
        if self.observation is not None:
            if self.status != self.observation.status:
                raise ValueError("Check status must match its observation")
        elif self.status not in {
            CheckRunStatus.READY,
            CheckRunStatus.UNCERTAIN,
            CheckRunStatus.REJECTED,
        }:
            raise ValueError("Known check status requires an observation")
        if self.evidence_recorded and self.status != CheckRunStatus.COMPLETED:
            raise ValueError("Only completed checks can have recorded evidence")
        if self.evidence_recorded and not self.reports_collected:
            raise ValueError("Check evidence requires completed report collection")
        if self.reports_collected:
            if (
                self.status != CheckRunStatus.COMPLETED
                or self.report_sources is None
                or tuple(report.source for report in self.reports) != self.report_sources
            ):
                raise ValueError("Collected reports must match the frozen source manifest")
        elif self.reports:
            raise ValueError("Check reports require completed collection")
        if self.report_sources is not None and len(
            {source.external_id for source in self.report_sources}
        ) != len(self.report_sources):
            raise ValueError("Report source identities must be unique")
        if self.report_sources is not None and self.status != CheckRunStatus.COMPLETED:
            raise ValueError("Only completed checks can admit report sources")
        if self.resolution is not None and (
            self.observation is None or self.resolution.external_id != self.observation.external_id
        ):
            raise ValueError("Check resolution must identify its observed provider run")
        if not self.plan.created_at <= self.created_at < self.plan.expires_at:
            raise ValueError("Check admission must precede the verification deadline")
        return self
