"""Observe root authority without redelivery, child projection or another lifecycle manager."""

from typing import Protocol

from mas.application.access.executions import ExecutionAccessUnavailable
from mas.application.execution.ports import (
    ExecutionError,
    ExecutionLocationUnavailable,
    ExecutionMissing,
)
from mas.core.identity import Identity
from mas.domain.execution.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    SubmissionState,
)


class RootExecutionRecords(Protocol):
    async def get(self, execution_id: str) -> ExecutionRecord: ...


class RootExecutionGateway(Protocol):
    @property
    def location(self) -> str: ...
    async def status(self, execution_id: str) -> ExecutionPhase: ...


class ExecutionGrantAccess:
    def __init__(self, records: RootExecutionRecords, gateway: RootExecutionGateway) -> None:
        self._records, self._gateway = records, gateway

    async def _record(self, execution_id: str, owner: Identity) -> ExecutionRecord:
        record = await self._records.get(execution_id)
        if not record.owner.owns(owner):
            raise PermissionError("Execution does not belong to this owner")
        return record

    async def _active(self, record: ExecutionRecord) -> bool:
        if record.cancel_requested or record.phase in TERMINAL_PHASES:
            return False
        if not record.location or record.location != self._gateway.location:
            raise ExecutionLocationUnavailable()
        phase = await self._gateway.status(record.engine_handle)
        if phase == ExecutionPhase.UNKNOWN:
            raise ExecutionLocationUnavailable()
        return phase not in TERMINAL_PHASES

    @staticmethod
    def _root(record: ExecutionRecord) -> bool:
        return (
            record.parent_execution_id is None
            and record.context.root_execution_id == record.execution_id
            and not record.context.ancestor_execution_ids
            and bool(record.context.engine_handle)
        )

    async def active(self, root_execution_id: str, owner: Identity) -> bool:
        try:
            record = await self._record(root_execution_id, owner)
            return self._root(record) and await self._active(record)
        except KeyError, PermissionError, ExecutionMissing:
            return False
        except ExecutionError:
            raise ExecutionAccessUnavailable() from None

    async def closed(self, root_execution_id: str, owner: Identity) -> bool:
        try:
            record = await self._record(root_execution_id, owner)
        except KeyError:
            return False
        except PermissionError:
            return True
        except ExecutionError:
            raise ExecutionAccessUnavailable() from None
        if not self._root(record) or record.cancel_requested or record.phase in TERMINAL_PHASES:
            return True
        try:
            return not await self._active(record)
        except ExecutionMissing:
            return record.submission == SubmissionState.ACCEPTED
        except ExecutionError:
            raise ExecutionAccessUnavailable() from None
