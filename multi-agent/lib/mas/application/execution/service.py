"""Async submission, recovery, ownership, and result projection for any program kind."""

import asyncio
import json
import logging
import math
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from uuid import uuid4

from jsonschema import Draft202012Validator, ValidationError
from pydantic import JsonValue
from referencing import Registry
from referencing.exceptions import Unresolvable

from mas.application.access.admission import WorkflowAccessAdmission, check_access_approval
from mas.application.access.credentials import WorkflowCredentialUnavailable
from mas.application.execution.models import PreparedExecution, StartExecution, SubmissionClaim
from mas.application.execution.ports import (
    ExecutionCancellation,
    ExecutionError,
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ExecutionRepository,
    ExecutionRequestConflict,
    ProgramExecutionGateway,
    SubmissionUnconfirmed,
)
from mas.application.programs.service import ProgramService
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccessApproval
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.identity import request_digest
from mas.domain.execution.models import (
    TERMINAL_PHASES,
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
    SubmissionState,
)
from mas.domain.json_values import portable_json

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        programs: ProgramService,
        records: ExecutionRepository,
        gateway: ProgramExecutionGateway,
        cancellation: ExecutionCancellation | None = None,
        *,
        submission_timeout_seconds: float = 30,
        clock: Callable[[], datetime] | None = None,
        workflow_access: WorkflowAccessAdmission | None = None,
    ) -> None:
        self._programs = programs
        self._records = records
        self._gateway = gateway
        self._cancellation = cancellation
        self._reconcile_cursor: str | None = None
        if not math.isfinite(submission_timeout_seconds) or submission_timeout_seconds <= 0:
            raise ValueError("Submission timeout must be finite and positive")
        self._submission_timeout = submission_timeout_seconds
        self._now = clock or partial(datetime.now, UTC)
        self._workflow_access = workflow_access

    def approve_workflow_access(
        self, request: StartExecution, owner: Identity, approved_by: Identity | None
    ) -> WorkflowAccessApproval | None:
        if not request.workflow_access:
            return None
        if approved_by is None:
            raise PermissionError("Workflow access requires authenticated human approval")
        if self._workflow_access is None:
            raise WorkflowCredentialUnavailable("Managed workflow access is not configured")
        return self._workflow_access.approve(request, owner, approved_by)

    async def start(
        self,
        request: StartExecution,
        caller: Identity,
        *,
        credential_user_id: str = "",
        context: ExecutionContext | None = None,
        approved_by: Identity | None = None,
        workflow_access_approval: WorkflowAccessApproval | None = None,
        prepared_template: PreparedExecution | None = None,
    ) -> ExecutionRecord:
        portable_json(request.inputs)
        request = StartExecution.model_validate_json(request.model_dump_json())
        if context is not None:
            context = ExecutionContext.model_validate_json(context.model_dump_json())
        if context is not None and (
            not context.identity.owns(caller) or context.session_id != (request.session_id or "")
        ):
            raise PermissionError("Execution context does not belong to the request owner/session")
        revision = await self._programs.revision(request.program, caller)
        try:
            Draft202012Validator(revision.definition.input_schema, registry=Registry()).validate(
                request.inputs
            )
        except ValidationError, Unresolvable, RecursionError:
            raise ValueError("Program input violates its contract") from None
        execution_id = request.execution_id or str(uuid4())
        try:
            existing = await self.get(execution_id, caller)
        except KeyError:
            existing = None
        if existing is not None:
            self._check_request(existing, request)
            if (
                workflow_access_approval is not None
                and workflow_access_approval != existing.workflow_access_approval
            ):
                raise PermissionError(
                    "Workflow access approval differs from the original invocation"
                )
            if context is not None and (existing.context.scope, existing.context.tags) != (
                context.scope,
                context.with_credential_user(credential_user_id).tags,
            ):
                raise ValueError("Execution context differs from the original request")
            return await self._recover(existing)
        request = request.model_copy(update={"execution_id": execution_id})
        approval = workflow_access_approval
        if approval is None:
            approval = self.approve_workflow_access(request, caller, approved_by)
        else:
            check_access_approval(request, caller, approval)
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
        prepared = (
            await self._gateway.prepare(revision, request.inputs, context, native_id)
            if prepared_template is None
            else await self._gateway.bind(
                prepared_template, revision, request.inputs, context, native_id
            )
        )
        record = ExecutionRecord(
            execution_id=execution_id,
            owner=caller,
            program=request.program,
            content_digest=revision.content_digest,
            inputs=request.inputs,
            context=context,
            location=prepared.location,
            work_limits=prepared.work_limits,
            admitted_profiles=prepared.admitted_profiles,
            workflow_access_approval=approval,
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
        if (record.program, record.session_id) != (
            request.program,
            request.session_id,
        ) or json.dumps(record.inputs, sort_keys=True, allow_nan=False) != json.dumps(
            request.inputs, sort_keys=True, allow_nan=False
        ):
            raise ExecutionRequestConflict(
                "Execution identity already belongs to a different request"
            )
        if record.workflow_access_approval is not None:
            check_access_approval(
                request.model_copy(update={"execution_id": record.execution_id}),
                record.owner,
                record.workflow_access_approval,
            )
        elif request.workflow_access:
            raise ValueError("Execution identity has no workflow access approval")

    async def _submit(self, record: ExecutionRecord, *, recover: bool = False) -> ExecutionRecord:
        self._require_location(record)
        now = self._now()
        claim = SubmissionClaim(
            token=uuid4().hex, expires_at=now + timedelta(seconds=self._submission_timeout + 5)
        )
        if not await self._records.claim_submission(
            record.execution_id, claim, now=now, recover=recover
        ):
            return await self._records.get(record.execution_id)
        try:
            async with asyncio.timeout(self._submission_timeout):
                prepared = await self._records.get_prepared(record.execution_id)
                if (
                    record.workflow_access_approval is not None
                    and not (await self._records.get(record.execution_id)).cancel_requested
                ):
                    if self._workflow_access is None:
                        raise SubmissionUnconfirmed(
                            ExecutionFailure(
                                kind=FailureKind.INFRASTRUCTURE,
                                message=(
                                    "Managed workflow access requires its original configuration"
                                ),
                                code="workflow_access_pending",
                                retryable=True,
                            )
                        )
                    await self._workflow_access.provision(record)
                latest = await self._records.get(record.execution_id)
                if latest.cancel_requested:
                    record = record.model_copy(
                        update={"phase": ExecutionPhase.CANCELLED, "cancel_requested": True}
                    )
                    await self._records.finish_submission(record, claim.token)
                    return await self._records.get(record.execution_id)
                await self._gateway.start(prepared, recover=recover)
        except SubmissionUnconfirmed, TimeoutError:
            record = record.model_copy(update={"submission": SubmissionState.UNCONFIRMED})
        except asyncio.CancelledError:
            record = record.model_copy(update={"submission": SubmissionState.UNCONFIRMED})
            await await_owned(self._records.finish_submission(record, claim.token))
            raise
        except ExecutionError as error:
            cancelled = (
                error.failure.code == "workflow_access_denied"
                and (await self._records.get(record.execution_id)).cancel_requested
            )
            record = record.model_copy(
                update={
                    "phase": ExecutionPhase.CANCELLED if cancelled else ExecutionPhase.FAILED,
                    "cancel_requested": record.cancel_requested or cancelled,
                    "submission": record.submission if cancelled else SubmissionState.REFUSED,
                    "failure": None if cancelled else error.failure,
                }
            )
        else:
            record = record.model_copy(
                update={
                    "phase": ExecutionPhase.RUNNING,
                    "submission": SubmissionState.ACCEPTED,
                }
            )
        await self._records.finish_submission(record, claim.token)
        latest = await self._records.get(record.execution_id)
        if latest.cancel_requested and latest.phase not in TERMINAL_PHASES:
            await self._cancel_native(latest, latest.owner)
        return await self._records.get(record.execution_id)

    async def _recover(self, record: ExecutionRecord) -> ExecutionRecord:
        if record.phase in TERMINAL_PHASES:
            return record
        self._require_location(record)
        if record.submission == SubmissionState.ACCEPTED:
            return record
        if record.submission == SubmissionState.PREPARED:
            return await self._submit(record)
        if record.submission == SubmissionState.STARTING:
            claim = await self._records.submission_claim(record.execution_id)
            if claim is not None and claim.expires_at > self._now():
                return record
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

    async def is_active(self, execution_id: str, caller: Identity) -> bool:
        """Observe an exact root or child without recovery or recursive projection."""
        record = await self.get(execution_id, caller)
        if record.cancel_requested or record.phase in TERMINAL_PHASES:
            return False
        self._require_location(record)
        phase = await self._gateway.status(record.engine_handle)
        if phase == ExecutionPhase.UNKNOWN:
            raise ExecutionLocationUnavailable()
        return phase not in TERMINAL_PHASES

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
        if record.cancel_requested and phase not in TERMINAL_PHASES:
            await self._gateway.cancel(record.engine_handle)
            phase = await self._gateway.status(record.engine_handle)
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
        await self._records.request_cancellation(execution_id)
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
        try:
            await self._gateway.cancel(record.engine_handle)
        except ExecutionMissing:
            # The durable cancellation intent is reconciled after admission is observable.
            return

    async def prevent_start(
        self,
        request: StartExecution,
        caller: Identity,
        context: ExecutionContext,
        *,
        workflow_access_approval: WorkflowAccessApproval | None = None,
    ) -> ExecutionRecord:
        """Atomically record cancellation even if submission has not created its record yet."""
        if request.execution_id is None:
            raise ValueError("Preventing a start requires a stable execution identity")
        if not context.identity.owns(caller) or context.session_id != (request.session_id or ""):
            raise PermissionError("Cancellation context does not match request")
        if workflow_access_approval is not None:
            check_access_approval(request, caller, workflow_access_approval)
        revision = await self._programs.revision(request.program, caller)
        record = ExecutionRecord(
            execution_id=request.execution_id,
            owner=caller,
            program=request.program,
            content_digest=revision.content_digest,
            inputs=request.inputs,
            workflow_access_approval=workflow_access_approval,
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
            cancel_requested=True,
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
