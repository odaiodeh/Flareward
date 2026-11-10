"""Trusted check dispatch is separate from workflow authority and scheduling."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.check_runs import CheckRun, CheckRunObservation
from lumora.services.verification.domain.models import (
    CheckId,
    CheckReportSource,
    VerificationId,
    VerifierId,
)


class CheckRunnerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owners: tuple[Identity, ...] = Field(min_length=1, max_length=128)
    policies: frozenset[str] = Field(min_length=1, max_length=128)
    check: CheckId
    verifier: VerifierId
    subject_kind: str = Field(min_length=1, max_length=128)


class StartCheckRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plan_id: VerificationId
    runner: str = Field(min_length=1, max_length=128)


class CheckRunHandle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent_id: VerificationId


class ResolveCheckRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    external_id: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1000)


class CheckSubmissionRejected(ValueError):
    """Provider definitively refused this submission; no automatic replacement."""


class CheckProviderUnavailable(RuntimeError):
    """Provider outcome is unavailable or ambiguous; submission must not be repeated."""


class CheckRunner(Protocol):
    @property
    def configuration_digest(self) -> str: ...

    def validate(self, run: CheckRun) -> None:
        """Validate candidate/configuration before acquiring submission ownership."""
        ...

    async def submit(self, run: CheckRun) -> CheckRunObservation: ...

    async def reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        """None means unresolved, never permission to resubmit."""
        ...


class CheckRunRepository(Protocol):
    async def create(self, run: CheckRun) -> bool: ...
    async def get(self, intent_id: str) -> CheckRun | None: ...
    async def save(self, run: CheckRun, *, expected_revision: int) -> bool: ...
    async def pending_jobs(self, *, after: str, limit: int) -> Sequence[CheckRun]: ...


class CheckJobControl(Protocol):
    async def stop(self, run: CheckRun) -> bool:
        """True requires the exact owned job to be terminal; uncertainty remains pending."""
        ...


class CheckReports(Protocol):
    async def list(self, run: CheckRun) -> tuple[CheckReportSource, ...]: ...
    def open(
        self, run: CheckRun, source: CheckReportSource
    ) -> AbstractAsyncContextManager[AsyncIterator[bytes]]: ...


class CheckRunGateway(Protocol):
    async def start_check(self, request: StartCheckRun) -> CheckRun: ...
    async def refresh_check(self, intent_id: str) -> CheckRun: ...
