"""Operator-pinned verifier Programs reuse normal execution and durable observations."""

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol, Self

from pydantic import Field, JsonValue, model_validator

from flareward.executions.domain.models import TERMINAL_PHASES, ExecutionPhase, ExecutionRecord
from flareward.executions.models import StartExecution
from flareward.executions.ports import ExecutionError, ExecutionMissing
from flareward.models import Model
from flareward.programs.domain.models import ProgramRef, ProgramRevision
from flareward.services.artifacts.access_models import ArtifactActor
from flareward.services.artifacts.domain.models import (
    BlobArtifactRef,
    ContentIdentity,
    InlineArtifact,
)
from flareward.services.artifacts.ports import ArtifactMissing
from flareward.services.identity.domain import Identity
from flareward.services.verification.check_ports import CheckProviderUnavailable, CheckRunnerPolicy
from flareward.services.verification.domain.check_runs import (
    CheckRun,
    CheckRunObservation,
    CheckRunStatus,
)
from flareward.services.verification.domain.models import (
    CheckId,
    CheckReportSource,
    CheckVerdict,
    VerificationId,
    VerificationSubject,
)


class CheckProgramInput(Model):
    intent_id: VerificationId
    plan_id: VerificationId
    check: CheckId
    subject: VerificationSubject
    artifact: InlineArtifact | None = None


class CheckProgramResult(Model):
    subject_fingerprint: VerificationId
    verdict: CheckVerdict
    details: JsonValue = None


class ProgramCheckConfiguration(Model):
    """Private operator trust binding, never chosen by an execution's input."""

    policy: CheckRunnerPolicy
    program_owner: Identity
    program: ProgramRef
    content_digest: VerificationId
    max_result_bytes: int = Field(default=65_536, ge=1, le=1_048_576)
    input_artifact_max_bytes: int | None = Field(default=None, ge=1, le=1_048_576)

    @model_validator(mode="after")
    def inline_subject(self) -> Self:
        if (
            self.input_artifact_max_bytes is not None
            and self.policy.subject_kind != "blob-artifact@1"
        ):
            raise ValueError("Inline verifier input requires a blob artifact policy")
        return self

    @property
    def digest(self) -> str:
        value = self.model_dump(mode="json")
        value["policy"]["policies"] = sorted(self.policy.policies)
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class CheckProgramExecutions(Protocol):
    async def start(self, request: StartExecution, caller: Identity) -> ExecutionRecord: ...
    async def refresh(self, execution_id: str, caller: Identity) -> ExecutionRecord: ...
    async def cancel(self, execution_id: str, caller: Identity) -> None: ...


class CheckProgramRevisions(Protocol):
    async def revision(self, reference: ProgramRef, caller: Identity) -> ProgramRevision: ...


class CheckProgramArtifacts(Protocol):
    def open(
        self, reference: BlobArtifactRef, actor: ArtifactActor
    ) -> AbstractAsyncContextManager[AsyncIterator[bytes]]: ...


class ProgramCheckRunner:
    """Observe a trusted Program; ordinary workflow output is never an attestation."""

    def __init__(
        self,
        config: ProgramCheckConfiguration,
        executions: CheckProgramExecutions,
        programs: CheckProgramRevisions,
        *,
        artifacts: CheckProgramArtifacts | None = None,
    ) -> None:
        self._config, self._executions, self._programs = config, executions, programs
        self._artifacts = artifacts
        if config.input_artifact_max_bytes is not None and artifacts is None:
            raise ValueError("Verifier input transport requires artifact storage")

    @property
    def configuration_digest(self) -> str:
        return self._config.digest

    @staticmethod
    def _identity(run: CheckRun) -> str:
        return "verification-" + run.intent_id

    @staticmethod
    def _input(run: CheckRun) -> CheckProgramInput:
        return CheckProgramInput(
            intent_id=run.intent_id,
            plan_id=run.plan.plan_id,
            check=run.check,
            subject=run.plan.subject,
        )

    @staticmethod
    def _artifact_reference(run: CheckRun) -> BlobArtifactRef:
        subject = run.plan.subject
        reference = BlobArtifactRef.model_validate(subject.identity)
        canonical = VerificationSubject(
            kind="blob-artifact@1", identity=reference.model_dump(mode="json")
        )
        if subject.fingerprint != canonical.fingerprint:
            raise ValueError("Verifier requires a canonical blob candidate identity")
        return reference

    def validate(self, run: CheckRun) -> None:
        policy = self._config.policy
        if (
            run.configuration_digest != self.configuration_digest
            or run.check != policy.check
            or run.verifier != policy.verifier
            or run.plan.policy not in policy.policies
            or run.plan.subject.kind != policy.subject_kind
            or not any(owner.owns(run.plan.owner) for owner in policy.owners)
        ):
            raise ValueError("Verifier Program does not admit this check")
        if self._config.input_artifact_max_bytes is not None:
            if run.plan.subject.kind != "blob-artifact@1":
                raise ValueError("Inline verifier input requires a blob artifact")
            reference = self._artifact_reference(run)
            if reference.size_bytes > self._config.input_artifact_max_bytes:
                raise ValueError("Verifier candidate exceeds its input byte limit")

    async def _prepared_input(self, run: CheckRun) -> CheckProgramInput:
        request = self._input(run)
        maximum = self._config.input_artifact_max_bytes
        if maximum is None:
            return request
        assert self._artifacts is not None
        reference = self._artifact_reference(run)
        content = bytearray()
        async with self._artifacts.open(reference, ArtifactActor(run.plan.owner)) as source:
            async for chunk in source:
                if len(content) + len(chunk) > min(reference.size_bytes, maximum):
                    raise ValueError("Verifier candidate exceeds its referenced byte limit")
                content.extend(chunk)
        inline = InlineArtifact(reference=reference, data=base64.b64encode(content).decode("ascii"))
        return request.model_copy(update={"artifact": inline})

    async def _binding(self) -> None:
        revision = await self._programs.revision(self._config.program, self._config.program_owner)
        if (
            revision.reference != self._config.program
            or revision.content_digest != self._config.content_digest
            or not revision.definition.owner.owns(self._config.program_owner)
        ):
            raise ValueError("Verifier Program differs from its operator trust binding")

    def _record(self, run: CheckRun, record: ExecutionRecord) -> None:
        actual = CheckProgramInput.model_validate(record.inputs)
        expected = self._input(run)
        if (
            record.execution_id != self._identity(run)
            or not record.owner.owns(self._config.program_owner)
            or record.program != self._config.program
            or record.content_digest != self._config.content_digest
            or record.parent_execution_id is not None
            or record.session_id is not None
            or record.workflow_access_approval is not None
            or record.context.root_execution_id != record.execution_id
            or actual.intent_id != expected.intent_id
            or actual.plan_id != expected.plan_id
            or actual.check != expected.check
            or actual.subject.fingerprint != expected.subject.fingerprint
        ):
            raise ValueError("Verifier execution differs from the admitted check")
        if self._config.input_artifact_max_bytes is not None:
            reference = self._artifact_reference(run)
            if actual.artifact is None or actual.artifact.reference != reference:
                raise ValueError("Verifier execution lacks its exact candidate content")
        elif actual.artifact is not None:
            raise ValueError("Verifier execution has unadmitted inline content")

    def _result(self, run: CheckRun, record: ExecutionRecord) -> CheckProgramResult:
        self._record(run, record)
        if record.phase != ExecutionPhase.COMPLETED or record.failure is not None:
            raise ValueError("Verifier Program has no completed result")
        encoded = json.dumps(record.result, allow_nan=False).encode()
        if len(encoded) > self._config.max_result_bytes:
            raise ValueError("Verifier Program result exceeds its byte limit")
        result = CheckProgramResult.model_validate(record.result)
        if result.subject_fingerprint != run.plan.subject.fingerprint:
            raise ValueError("Verifier Program evaluated a different candidate")
        return result

    def _observation(self, run: CheckRun, record: ExecutionRecord) -> CheckRunObservation:
        self._record(run, record)
        phase = record.phase
        if phase == ExecutionPhase.UNKNOWN:
            raise CheckProviderUnavailable("Verifier Program observation is unavailable")
        completed = phase in {
            ExecutionPhase.COMPLETED,
            ExecutionPhase.FAILED,
            ExecutionPhase.CANCELLED,
        }
        verdict = (
            self._result(run, record).verdict
            if phase == ExecutionPhase.COMPLETED
            else CheckVerdict.ERROR
            if completed
            else None
        )
        return CheckRunObservation(
            external_id=record.execution_id,
            status=CheckRunStatus.COMPLETED if completed else CheckRunStatus.RUNNING,
            verdict=verdict,
        )

    async def submit(self, run: CheckRun) -> CheckRunObservation:
        self.validate(run)
        try:
            await self._binding()
            inputs = await self._prepared_input(run)
            record = await self._executions.start(
                StartExecution(
                    program=self._config.program,
                    execution_id=self._identity(run),
                    inputs=inputs.model_dump(
                        mode="json", exclude={"artifact"} if inputs.artifact is None else set()
                    ),
                ),
                self._config.program_owner,
            )
            return self._observation(run, record)
        except (
            ArtifactMissing,
            ExecutionError,
            ExecutionMissing,
            KeyError,
            PermissionError,
            ValueError,
        ):
            raise CheckProviderUnavailable("Verifier Program submission is unconfirmed") from None

    async def reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        self.validate(run)
        try:
            await self._binding()
            record = await self._executions.refresh(self._identity(run), self._config.program_owner)
            return self._observation(run, record)
        except KeyError:
            return None  # Absence never authorizes another start.
        except ExecutionError, ExecutionMissing, PermissionError, ValueError:
            raise CheckProviderUnavailable("Verifier Program observation is unavailable") from None

    async def stop(self, run: CheckRun) -> bool:
        self.validate(run)
        try:
            await self._binding()
            identity, owner = self._identity(run), self._config.program_owner
            record = await self._executions.refresh(identity, owner)
            self._record(run, record)
            if record.phase in TERMINAL_PHASES:
                return True
            if record.phase == ExecutionPhase.UNKNOWN:
                return False
            await self._executions.cancel(identity, owner)
            record = await self._executions.refresh(identity, owner)
            self._record(run, record)
            return record.phase in TERMINAL_PHASES
        except KeyError:
            return False
        except ExecutionError, ExecutionMissing, PermissionError, ValueError:
            raise CheckProviderUnavailable("Verifier Program closure is unconfirmed") from None

    async def _report(self, run: CheckRun) -> bytes:
        self.validate(run)
        try:
            await self._binding()
            record = await self._executions.refresh(self._identity(run), self._config.program_owner)
            if record.phase in {ExecutionPhase.FAILED, ExecutionPhase.CANCELLED}:
                self._record(run, record)
                result = CheckProgramResult(
                    subject_fingerprint=run.plan.subject.fingerprint,
                    verdict=CheckVerdict.ERROR,
                    details={"execution_phase": record.phase.value},
                )
            else:
                result = self._result(run, record)
            report = result.model_dump_json().encode()
            if len(report) > self._config.max_result_bytes:
                raise ValueError("Verifier Program report exceeds its byte limit")
            return report
        except ExecutionError, ExecutionMissing, KeyError, PermissionError, ValueError:
            raise CheckProviderUnavailable("Verifier Program report is unavailable") from None

    @staticmethod
    def _source(run: CheckRun, report: bytes) -> CheckReportSource:
        return CheckReportSource(
            external_id="verification-report:" + run.intent_id,
            name="check.json",
            media_type="application/json",
            identity=ContentIdentity(
                sha256=hashlib.sha256(report).hexdigest(), size_bytes=len(report)
            ),
        )

    async def list(self, run: CheckRun) -> tuple[CheckReportSource, ...]:
        report = await self._report(run)
        return (self._source(run, report),)

    @asynccontextmanager
    async def open(
        self, run: CheckRun, source: CheckReportSource
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        report = await self._report(run)
        if source != self._source(run, report):
            raise CheckProviderUnavailable("Verifier Program report differs from its manifest")

        async def chunks() -> AsyncIterator[bytes]:
            yield report

        yield chunks()
