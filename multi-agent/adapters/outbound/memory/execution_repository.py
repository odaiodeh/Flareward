"""Development execution records with atomic admission and detached readers."""

import asyncio

from mas.execution.identity import request_digest
from mas.execution.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    PreparedExecution,
    SubmissionState,
)


class MemoryExecutionRepository:
    def __init__(self) -> None:
        self._records: dict[str, str] = {}
        self._prepared: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        record: ExecutionRecord,
        prepared: PreparedExecution | None = None,
    ) -> bool:
        async with self._lock:
            if record.execution_id in self._records:
                return False
            self._records[record.execution_id] = record.model_dump_json()
            if prepared is not None:
                self._prepared[record.execution_id] = prepared.model_dump_json()
            return True

    async def get_prepared(self, execution_id: str) -> PreparedExecution:
        return PreparedExecution.model_validate_json(self._prepared[execution_id])

    async def claim_submission(self, execution_id: str) -> bool:
        async with self._lock:
            record = await self.get(execution_id)
            if record.submission != SubmissionState.PREPARED or record.phase in TERMINAL_PHASES:
                return False
            record = record.model_copy(update={"submission": SubmissionState.STARTING})
            self._records[execution_id] = record.model_dump_json()
            return True

    async def cancel_prepared(self, execution_id: str) -> bool:
        async with self._lock:
            record = await self.get(execution_id)
            if record.submission != SubmissionState.PREPARED or record.phase in TERMINAL_PHASES:
                return False
            record = record.model_copy(update={"phase": ExecutionPhase.CANCELLED})
            self._records[execution_id] = record.model_dump_json()
            return True

    async def pending(
        self,
        limit: int = 100,
        *,
        after_execution_id: str | None = None,
    ) -> list[ExecutionRecord]:
        records = [ExecutionRecord.model_validate_json(value) for value in self._records.values()]
        return [
            record
            for record in sorted(records, key=lambda value: value.execution_id)
            if record.phase not in TERMINAL_PHASES
            and (after_execution_id is None or record.execution_id > after_execution_id)
        ][:limit]

    async def get(self, execution_id: str) -> ExecutionRecord:
        return ExecutionRecord.model_validate_json(self._records[execution_id])

    async def children(self, execution_id: str) -> list[ExecutionRecord]:
        records = [ExecutionRecord.model_validate_json(value) for value in self._records.values()]
        return sorted(
            (record for record in records if record.parent_execution_id == execution_id),
            key=lambda record: record.execution_id,
        )

    async def update(self, record: ExecutionRecord) -> None:
        async with self._lock:
            current = await self.get(record.execution_id)
            if request_digest(current) != request_digest(record):
                raise ValueError("Execution request identity cannot be changed")
            if current.phase in TERMINAL_PHASES and record.phase != current.phase:
                return
            if current.submission == SubmissionState.ACCEPTED and record.submission in {
                SubmissionState.PREPARED,
                SubmissionState.STARTING,
                SubmissionState.UNCONFIRMED,
            }:
                return
            self._records[record.execution_id] = record.model_dump_json()
