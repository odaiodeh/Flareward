"""Bounded application observation projection; native execution remains engine-owned."""

from lumora.executions.domain.observation import (
    CallOccurrence,
    ExecutionObservation,
    OccurrenceKind,
    OccurrenceStatus,
)


class OccurrenceProjection:
    def __init__(self, execution_id: str, *, capacity: int = 256) -> None:
        if capacity < 1:
            raise ValueError("Observation capacity must be positive")
        self._execution_id = execution_id
        self._capacity = capacity
        self._total = 0
        self._revision = 0
        self._calls: dict[int, CallOccurrence] = {}

    def start(
        self,
        call_site: str,
        kind: OccurrenceKind,
        *,
        graph_step: int | None = None,
        attempt: int = 1,
    ) -> int:
        self._total += 1
        self._revision += 1
        self._calls[self._total] = CallOccurrence(
            ordinal=self._total,
            call_site=call_site,
            kind=kind,
            graph_step=graph_step,
            attempt=attempt,
        )
        if len(self._calls) > self._capacity:
            del self._calls[next(iter(self._calls))]
        return self._total

    def finish(self, ordinal: int, status: OccurrenceStatus) -> None:
        call = self._calls.get(ordinal)
        if call is not None and call.status != status:
            self._calls[ordinal] = call.model_copy(update={"status": status})
            self._revision += 1

    def bind_child(self, ordinal: int, execution_id: str) -> None:
        call = self._calls.get(ordinal)
        if call is not None:
            self._calls[ordinal] = call.model_copy(update={"child_execution_id": execution_id})
            self._revision += 1

    def snapshot(self) -> ExecutionObservation:
        return ExecutionObservation(
            execution_id=self._execution_id,
            revision=self._revision,
            total=self._total,
            truncated=self._total > len(self._calls),
            occurrences=tuple(self._calls.values()),
        )
