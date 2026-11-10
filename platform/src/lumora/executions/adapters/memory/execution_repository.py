"""Development execution records with atomic admission and detached readers."""

import asyncio
from datetime import datetime

from lumora.executions.domain.identity import request_digest
from lumora.executions.domain.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    SubmissionState,
)
from lumora.executions.models import PreparedExecution, SubmissionClaim


class MemoryExecutionRepository:
    def __init__(self) -> None:
        self._records: dict[str, str] = {}
        self._prepared: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._claims: dict[str, SubmissionClaim] = {}
        self._cancel_requested: set[str] = set()

    async def create(
        self,
        record: ExecutionRecord,
        prepared: PreparedExecution | None = None,
    ) -> bool:
        async with self._lock:
            if record.execution_id in self._records:
                return False
            self._records[record.execution_id] = record.model_dump_json()
            if record.cancel_requested:
                self._cancel_requested.add(record.execution_id)
            if prepared is not None:
                self._prepared[record.execution_id] = prepared.model_dump_json()
            return True

    async def get_prepared(self, execution_id: str) -> PreparedExecution:
        return PreparedExecution.model_validate_json(self._prepared[execution_id])

    async def claim_submission(
        self, execution_id: str, claim: SubmissionClaim, *, now: datetime, recover: bool = False
    ) -> bool:
        if claim.expires_at <= now:
            raise ValueError("Submission claim must have a future deadline")
        async with self._lock:
            record = await self.get(execution_id)
            current = self._claims.get(execution_id)
            allowed = (
                record.submission == SubmissionState.PREPARED
                if not recover
                else record.submission == SubmissionState.UNCONFIRMED
                or (
                    record.submission == SubmissionState.STARTING
                    and (current is None or current.expires_at <= now)
                )
            )
            if not allowed or record.phase in TERMINAL_PHASES:
                return False
            record = record.model_copy(update={"submission": SubmissionState.STARTING})
            self._records[execution_id] = record.model_dump_json()
            self._claims[execution_id] = claim
            return True

    async def submission_claim(self, execution_id: str) -> SubmissionClaim | None:
        return self._claims.get(execution_id)

    async def finish_submission(self, record: ExecutionRecord, token: str) -> bool:
        async with self._lock:
            claim = self._claims.get(record.execution_id)
            if claim is None or claim.token != token:
                return False
            self._claims.pop(record.execution_id)
            return await self._update(record)

    async def request_cancellation(self, execution_id: str) -> None:
        async with self._lock:
            record = await self.get(execution_id)
            if record.phase not in TERMINAL_PHASES:
                self._cancel_requested.add(execution_id)

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
        records = [await self.get(key) for key in tuple(self._records)]
        return [
            record
            for record in sorted(records, key=lambda value: value.execution_id)
            if record.phase not in TERMINAL_PHASES
            and (after_execution_id is None or record.execution_id > after_execution_id)
        ][:limit]

    async def get(self, execution_id: str) -> ExecutionRecord:
        record = ExecutionRecord.model_validate_json(self._records[execution_id])
        return record.model_copy(
            update={"cancel_requested": execution_id in self._cancel_requested}
        )

    async def children(self, execution_id: str) -> list[ExecutionRecord]:
        records = [await self.get(key) for key in tuple(self._records)]
        return sorted(
            (record for record in records if record.parent_execution_id == execution_id),
            key=lambda record: record.execution_id,
        )

    async def update(self, record: ExecutionRecord) -> None:
        async with self._lock:
            await self._update(record)

    async def _update(self, record: ExecutionRecord) -> bool:
        current = await self.get(record.execution_id)
        if request_digest(current) != request_digest(record):
            raise ValueError("Execution request identity cannot be changed")
        if current.phase in TERMINAL_PHASES and record.phase != current.phase:
            return False
        if current.submission == SubmissionState.ACCEPTED and record.submission in {
            SubmissionState.PREPARED,
            SubmissionState.STARTING,
            SubmissionState.UNCONFIRMED,
            SubmissionState.REFUSED,
        }:
            return False
        self._records[record.execution_id] = record.model_dump_json()
        return True
