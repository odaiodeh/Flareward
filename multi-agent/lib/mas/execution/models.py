"""Engine-independent lifecycle and failure data."""

import hashlib
import json
from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, model_validator

from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.programs.models import Model, ProgramRef


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


class PreparedExecution(Model):
    """Opaque adapter snapshot; application services persist it without interpreting it."""

    format: str
    payload_json: str
    location: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        value = json.loads(self.payload_json)
        if self.location:
            value = {"location": self.location, "request": value}
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Prepared execution content digest mismatch")
        object.__setattr__(self, "content_digest", digest)
        return self


class ExecutionFailure(Model):
    kind: FailureKind
    message: str
    code: str | None = None
    retryable: bool = False


class ExecutionRecord(Model):
    execution_id: str
    owner: Identity
    program: ProgramRef
    inputs: JsonValue
    context: ExecutionContext
    location: str = ""
    phase: ExecutionPhase = ExecutionPhase.SUBMITTING
    submission: SubmissionState = SubmissionState.PREPARED
    session_id: str | None = None
    parent_execution_id: str | None = None
    result: JsonValue = None
    failure: ExecutionFailure | None = None

    @model_validator(mode="after")
    def validate_context(self) -> Self:
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


class StartExecution(Model):
    program: ProgramRef
    inputs: JsonValue = Field(default_factory=dict)
    execution_id: str | None = Field(default=None, min_length=1)
    session_id: str | None = None
