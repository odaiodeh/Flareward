"""Submission operations are separate from operations inside a running program."""

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import JsonValue

from mas.core.execution_context import ExecutionContext
from mas.execution.models import (
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
    PreparedExecution,
)
from mas.programs.models import ProgramRevision


class ExecutionError(Exception):
    def __init__(self, failure: ExecutionFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


class SubmissionUnconfirmed(ExecutionError):
    """A submitted execution may have started; recover using the persisted snapshot."""


class ExecutionMissing(LookupError):
    """The selected host has no execution with this handle."""


class ExecutionLocationUnavailable(ExecutionError):
    """The original location must be restored; this is not an execution failure."""

    def __init__(self) -> None:
        super().__init__(
            ExecutionFailure(
                kind=FailureKind.INFRASTRUCTURE,
                code="execution_location_unavailable",
                message=(
                    "Execution requires its original coordination location "
                    "and submission configuration"
                ),
                retryable=False,
            )
        )


class ExecutionCancellation(Protocol):
    """Release application waits before infrastructure drains an invocation."""

    async def cancel(self, execution_id: str, *, root_execution_id: str | None = None) -> None: ...


class ProgramExecutionPreparer(Protocol):
    async def prepare(
        self,
        revision: ProgramRevision,
        inputs: JsonValue,
        context: ExecutionContext,
        execution_id: str,
    ) -> PreparedExecution: ...


class ProgramExecutionGateway(ProgramExecutionPreparer, Protocol):
    @property
    def location(self) -> str:
        """Opaque identity of the configured coordination location and submission policy."""
        ...

    async def start(self, prepared: PreparedExecution, *, recover: bool = False) -> None: ...
    async def status(self, execution_id: str) -> ExecutionPhase: ...
    async def result(self, execution_id: str) -> JsonValue: ...
    async def cancel(self, execution_id: str) -> None: ...
    async def send(self, execution_id: str, name: str, data: JsonValue) -> None: ...
    async def children(self, execution_id: str) -> list[ExecutionRecord]: ...
    def events(self, execution_id: str, after_sequence: int = 0) -> AsyncIterator[JsonValue]: ...
    async def close(self) -> None: ...


class ExecutionRepository(Protocol):
    async def create(
        self,
        record: ExecutionRecord,
        prepared: PreparedExecution | None = None,
    ) -> bool: ...
    async def get(self, execution_id: str) -> ExecutionRecord: ...
    async def get_prepared(self, execution_id: str) -> PreparedExecution: ...
    async def children(self, execution_id: str) -> list[ExecutionRecord]: ...
    async def claim_submission(self, execution_id: str) -> bool: ...
    async def cancel_prepared(self, execution_id: str) -> bool: ...
    async def pending(
        self,
        limit: int = 100,
        *,
        after_execution_id: str | None = None,
    ) -> list[ExecutionRecord]: ...
    async def update(self, record: ExecutionRecord) -> None: ...
