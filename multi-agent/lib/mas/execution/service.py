"""Async submission, recovery, ownership, and result projection for any program kind."""

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import JsonValue

from mas.core.async_work import await_owned
from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.execution.identity import request_digest
from mas.execution.models import (
    TERMINAL_PHASES,
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
    StartExecution,
    SubmissionState,
)
from mas.execution.ports import (
    ExecutionCancellation,
    ExecutionError,
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ExecutionRepository,
    ProgramExecutionGateway,
    SubmissionUnconfirmed,
)
from mas.programs.service import ProgramService

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        programs: ProgramService,
        records: ExecutionRepository,
        gateway: ProgramExecutionGateway,
        cancellation: ExecutionCancellation | None = None,
    ) -> None:
        self._programs = programs
        self._records = records
        self._gateway = gateway
        self._cancellation = cancellation
        self._reconcile_cursor: str | None = None

    async def start(
        self,
        request: StartExecution,
        caller: Identity,
        *,
        credential_user_id: str = "",
        context: ExecutionContext | None = None,
    ) -> ExecutionRecord:
        request = StartExecution.model_validate_json(request.model_dump_json())
        if context is not None:
            context = ExecutionContext.model_validate_json(context.model_dump_json())
        if context is not None and (
            not context.identity.owns(caller) or context.session_id != (request.session_id or "")
        ):
            raise PermissionError("Execution context does not belong to the request owner/session")
        revision = await self._programs.revision(request.program, caller)
        Draft202012Validator(revision.definition.input_schema).validate(request.inputs)
        execution_id = request.execution_id or str(uuid4())
        try:
            existing = await self.get(execution_id, caller)
        except KeyError:
            existing = None
        if existing is not None:
            self._check_request(existing, request)
            if context is not None and (existing.context.scope, existing.context.tags) != (
                context.scope,
                context.with_credential_user(credential_user_id).tags,
            ):
                raise ValueError("Execution context differs from the original request")
            return await self._recover(existing)
        # Clients choose an idempotency key, never the native run identity.
        native_id = f"unifai-{uuid4().hex}"
        context = (context or ExecutionContext(identity=caller)).model_copy(
            update={
                "session_id": request.session_id or "",
                "execution_id": execution_id,
                "root_execution_id": execution_id,
                "parent_execution_id": None,
                "ancestor_execution_ids": (),
                "engine_name": "run_engine",
                "engine_handle": native_id,
            }
        )
        context = context.with_credential_user(credential_user_id)
        prepared = await self._gateway.prepare(revision, request.inputs, context, native_id)
        record = ExecutionRecord(
            execution_id=execution_id,
            owner=caller,
            program=request.program,
            inputs=request.inputs,
            context=context,
            location=prepared.location,
            session_id=request.session_id,
        )
        if not await self._records.create(record, prepared):
            existing = await self.get(execution_id, caller)
            self._check_request(existing, request)
            if context is not None and (existing.context.scope, existing.context.tags) != (
                context.scope,
                context.tags,
            ):
                raise ValueError("Execution context differs from the original request")
            return await self._recover(existing)
        return await self._submit(record)

    @staticmethod
    def _check_request(record: ExecutionRecord, request: StartExecution) -> None:
        if record.parent_execution_id is not None:
            raise ValueError("Execution identity belongs to a child, not a root submission")
        if (record.program, record.inputs, record.session_id) != (
            request.program,
            request.inputs,
            request.session_id,
        ):
            raise ValueError("Execution identity already belongs to a different request")

    async def _submit(self, record: ExecutionRecord, *, recover: bool = False) -> ExecutionRecord:
        self._require_location(record)
        if not recover and not await self._records.claim_submission(record.execution_id):
            return await self._records.get(record.execution_id)
        prepared = await self._records.get_prepared(record.execution_id)
        try:
            await self._gateway.start(prepared, recover=recover)
        except SubmissionUnconfirmed:
            record = record.model_copy(update={"submission": SubmissionState.UNCONFIRMED})
        except asyncio.CancelledError:
            record = record.model_copy(update={"submission": SubmissionState.UNCONFIRMED})
            await await_owned(self._records.update(record))
            raise
        except ExecutionError as error:
            record = record.model_copy(
                update={
                    "phase": ExecutionPhase.FAILED,
                    "submission": SubmissionState.REFUSED,
                    "failure": error.failure,
                }
            )
        else:
            record = record.model_copy(
                update={
                    "phase": ExecutionPhase.RUNNING,
                    "submission": SubmissionState.ACCEPTED,
                }
            )
        await self._records.update(record)
        return await self._records.get(record.execution_id)

    async def _recover(self, record: ExecutionRecord) -> ExecutionRecord:
        if record.phase in TERMINAL_PHASES:
            return record
        self._require_location(record)
        if record.submission == SubmissionState.ACCEPTED:
            return record
        if record.submission == SubmissionState.PREPARED:
            return await self._submit(record)
        try:
            await self._gateway.status(record.engine_handle)
        except ExecutionMissing:
            # Redeliver the identical persisted request under the private native ID.
            return await self._submit(record, recover=True)
        record = record.model_copy(update={"submission": SubmissionState.ACCEPTED})
        await self._records.update(record)
        return await self.refresh(record.execution_id, record.owner)

    async def get(self, execution_id: str, caller: Identity) -> ExecutionRecord:
        record = await self._records.get(execution_id)
        if not record.owner.owns(caller):
            raise PermissionError(execution_id)
        return record

    async def refresh(self, execution_id: str, caller: Identity) -> ExecutionRecord:
        record = await self.get(execution_id, caller)
        if record.phase in TERMINAL_PHASES:
            return record
        self._require_location(record)
        try:
            phase = await self._gateway.status(record.engine_handle)
        except ExecutionMissing:
            if record.submission != SubmissionState.ACCEPTED:
                return await self._recover(record)
            # Accepted work is never redelivered merely because its observation vanished.
            record = record.model_copy(
                update={
                    "phase": ExecutionPhase.UNKNOWN,
                    "failure": ExecutionFailure(
                        kind=FailureKind.INFRASTRUCTURE,
                        code="execution_observation_unavailable",
                        message="The accepted execution is no longer observable",
                    ),
                }
            )
            await self._records.update(record)
            return await self._records.get(execution_id)
        record = record.model_copy(
            update={
                "phase": phase,
                "submission": SubmissionState.ACCEPTED,
                "failure": None,
            }
        )
        if phase == ExecutionPhase.COMPLETED:
            record = record.model_copy(
                update={"result": await self._gateway.result(record.engine_handle)}
            )
        elif phase == ExecutionPhase.FAILED:
            try:
                await self._gateway.result(record.engine_handle)
            except ExecutionError as error:
                record = record.model_copy(update={"failure": error.failure})
        await self._discover_children(record)
        await self._records.update(record)
        return await self._records.get(execution_id)

    async def result(self, execution_id: str, caller: Identity) -> ExecutionRecord:
        record = await self.get(execution_id, caller)
        if record.phase in TERMINAL_PHASES:
            return record
        record = await self._recover(record)
        if record.phase in TERMINAL_PHASES:
            return record
        try:
            result = await self._gateway.result(record.engine_handle)
            record = record.model_copy(
                update={"phase": ExecutionPhase.COMPLETED, "result": result, "failure": None}
            )
        except ExecutionError as error:
            record = record.model_copy(
                update={"phase": ExecutionPhase.FAILED, "failure": error.failure}
            )
        except ExecutionMissing:
            return await self.refresh(execution_id, caller)
        except asyncio.CancelledError:
            if await self._gateway.status(record.engine_handle) != ExecutionPhase.CANCELLED:
                raise
            record = record.model_copy(update={"phase": ExecutionPhase.CANCELLED, "failure": None})
        await self._discover_children(record)
        await self._records.update(record)
        return await self._records.get(execution_id)

    async def _discover_children(self, parent: ExecutionRecord) -> None:
        for child in await self._gateway.children(parent.engine_handle):
            if (
                child.parent_execution_id != parent.execution_id
                or child.context.root_execution_id != parent.context.root_execution_id
                or child.session_id != parent.session_id
                or not child.owner.owns(parent.owner)
                or child.location != parent.location
                or child.execution_id
                in (parent.execution_id, *parent.context.ancestor_execution_ids)
            ):
                raise ValueError("Observed child execution does not belong to its parent")
            if not await self._records.create(child):
                existing = await self._records.get(child.execution_id)
                if request_digest(existing) != request_digest(child):
                    raise ValueError("Child execution identity already belongs to another request")
            await self.refresh(child.execution_id, parent.owner)

    async def children(self, execution_id: str, caller: Identity) -> list[ExecutionRecord]:
        await self.refresh(execution_id, caller)
        return await self._records.children(execution_id)

    async def cancel(self, execution_id: str, caller: Identity) -> None:
        record = await self.get(execution_id, caller)
        if record.phase in TERMINAL_PHASES:
            return
        self._require_location(record)
        try:
            if self._cancellation is not None:
                await self._cancellation.cancel(
                    execution_id, root_execution_id=record.context.root_execution_id or execution_id
                )
        finally:
            await self._cancel_native(record, caller)

    async def _cancel_native(self, record: ExecutionRecord, caller: Identity) -> None:
        if await self._records.cancel_prepared(record.execution_id):
            return
        record = await self._recover(record)
        if record.phase in TERMINAL_PHASES:
            return
        await self._gateway.cancel(record.engine_handle)

    async def prevent_start(
        self,
        request: StartExecution,
        caller: Identity,
        context: ExecutionContext,
    ) -> ExecutionRecord:
        """Atomically record cancellation even if submission has not created its record yet."""
        if request.execution_id is None:
            raise ValueError("Preventing a start requires a stable execution identity")
        if not context.identity.owns(caller) or context.session_id != (request.session_id or ""):
            raise PermissionError("Cancellation context does not match request")
        await self._programs.revision(request.program, caller)
        record = ExecutionRecord(
            execution_id=request.execution_id,
            owner=caller,
            program=request.program,
            inputs=request.inputs,
            context=context.model_copy(
                update={
                    "engine_name": "run_engine",
                    "engine_handle": f"unifai-{uuid4().hex}",
                    "execution_id": request.execution_id,
                    "root_execution_id": request.execution_id,
                    "parent_execution_id": None,
                    "ancestor_execution_ids": (),
                }
            ),
            session_id=request.session_id,
            phase=ExecutionPhase.CANCELLED,
        )
        if await self._records.create(record):
            return record
        existing = await self.get(request.execution_id, caller)
        self._check_request(existing, request)
        await self.cancel(request.execution_id, caller)
        return await self.refresh(request.execution_id, caller)

    async def send(self, execution_id: str, name: str, data: JsonValue, caller: Identity) -> None:
        record = await self.get(execution_id, caller)
        self._require_location(record)
        await self._gateway.send(record.engine_handle, name, data)

    async def events(
        self,
        execution_id: str,
        caller: Identity,
        after_sequence: int = 0,
    ) -> AsyncIterator[JsonValue]:
        record = await self.get(execution_id, caller)
        self._require_location(record)
        async for event in self._gateway.events(record.engine_handle, after_sequence):
            yield event

    def _require_location(self, record: ExecutionRecord) -> None:
        if not record.location or record.location != self._gateway.location:
            raise ExecutionLocationUnavailable()

    async def reconcile_pending(self, limit: int = 100) -> list[ExecutionRecord]:
        results = []
        records = await self._records.pending(limit, after_execution_id=self._reconcile_cursor)
        if not records and self._reconcile_cursor is not None:
            self._reconcile_cursor = None
            records = await self._records.pending(limit)
        for record in records:
            self._reconcile_cursor = record.execution_id
            try:
                results.append(await self.refresh(record.execution_id, record.owner))
            except Exception:
                logger.exception("Execution reconciliation failed for %s", record.execution_id)
        return results

    async def close(self) -> None:
        await self._gateway.close()
