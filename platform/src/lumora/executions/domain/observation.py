"""Application observation values contain identity and lifecycle, never work payloads."""

from enum import StrEnum

from pydantic import Field

from lumora.models import Model


class OccurrenceKind(StrEnum):
    OPERATION = "operation"
    ELEMENT = "element"
    PROGRAM = "program"


class OccurrenceStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CallOccurrence(Model):
    ordinal: int = Field(ge=1)
    call_site: str = Field(min_length=1)
    kind: OccurrenceKind
    status: OccurrenceStatus = OccurrenceStatus.RUNNING
    graph_step: int | None = Field(default=None, ge=0)
    attempt: int = Field(default=1, ge=1)
    child_execution_id: str | None = None


class ExecutionObservation(Model):
    execution_id: str
    revision: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    truncated: bool = False
    occurrences: tuple[CallOccurrence, ...] = ()


class OccurrencePage(ExecutionObservation):
    next_cursor: int | None = Field(default=None, ge=1)
