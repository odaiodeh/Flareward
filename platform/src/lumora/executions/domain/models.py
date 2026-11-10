"""Execution lifecycle and ownership invariants, independent of delivery adapters."""

from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, model_validator

from lumora.executions.domain.access import WorkflowAccessApproval
from lumora.executions.domain.budgets import WorkLimits
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.preferences import ExecutionProfileCatalog
from lumora.models import Model
from lumora.programs.domain.models import BodyPath, ProgramRef
from lumora.services.identity.domain import Identity


class ExecutionPhase(StrEnum):
    SUBMITTING = "submitting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


TERMINAL_PHASES = frozenset(
    {
        ExecutionPhase.COMPLETED,
        ExecutionPhase.FAILED,
        ExecutionPhase.CANCELLED,
    }
)


class FailureKind(StrEnum):
    APPLICATION = "application"
    CONTRACT = "contract"
    INFRASTRUCTURE = "infrastructure"


class SubmissionState(StrEnum):
    PREPARED = "prepared"
    STARTING = "starting"
    UNCONFIRMED = "unconfirmed"
    ACCEPTED = "accepted"
    REFUSED = "refused"


class ExecutionFailure(Model):
    kind: FailureKind
    message: str
    code: str | None = None
    retryable: bool = False


class ExecutionRecord(Model):
    execution_id: str
    owner: Identity
    program: ProgramRef
    body_path: BodyPath = ()
    content_digest: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")
    inputs: JsonValue
    context: ExecutionContext
    work_limits: WorkLimits | None = None
    admitted_profiles: ExecutionProfileCatalog | None = None
    workflow_access_approval: WorkflowAccessApproval | None = None
    location: str = ""
    phase: ExecutionPhase = ExecutionPhase.SUBMITTING
    submission: SubmissionState = SubmissionState.PREPARED
    session_id: str | None = None
    parent_execution_id: str | None = None
    result: JsonValue = None
    failure: ExecutionFailure | None = None
    cancel_requested: bool = False

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        approval = self.workflow_access_approval
        if approval is not None and (
            not approval.owner.owns(self.owner)
            or approval.root_execution_id != self.execution_id
            or self.parent_execution_id is not None
        ):
            raise ValueError("Workflow access approval belongs to a different root/owner")
        if self.body_path and self.parent_execution_id is None:
            raise ValueError("Owned program bodies require a parent execution")
        if self.body_path and not self.content_digest:
            raise ValueError("Owned program bodies require an immutable source digest")
        if not self.owner.owns(self.context.identity):
            raise ValueError("Execution context identity must match its owner")
        if (self.session_id or "") != self.context.session_id:
            raise ValueError("Execution context session identity must match its record")
        if self.context.execution_id and self.context.execution_id != self.execution_id:
            raise ValueError("Execution context identity must match its record")
        if self.parent_execution_id != self.context.parent_execution_id:
            raise ValueError("Execution parent identity must match its context")
        ancestors = self.context.ancestor_execution_ids
        if ancestors and (
            ancestors[0] != self.context.root_execution_id
            or ancestors[-1] != self.parent_execution_id
            or len(ancestors) != len(set(ancestors))
            or self.execution_id in ancestors
        ):
            raise ValueError("Execution ancestry must describe its root and immediate parent")
        return self

    @property
    def engine_handle(self) -> str:
        if not self.context.engine_handle:
            raise ValueError("Execution has no infrastructure handle")
        return self.context.engine_handle
