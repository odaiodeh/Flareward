"""Idempotent business-record admission for an already started scheduled run."""

import hashlib

from mas.core.execution_context import ExecutionContext
from mas.execution.identity import request_digest
from mas.execution.models import (
    ExecutionPhase,
    ExecutionRecord,
    PreparedExecution,
    StartExecution,
    SubmissionState,
)
from mas.execution.ports import ExecutionRepository
from mas.scheduling.programs import ProgramSchedule, stage_schedule
from mas.session.execution.session_store import SessionConflict, SessionStore


def scheduled_execution_id(native_id: str) -> str:
    return "scheduled-" + hashlib.sha256(native_id.encode()).hexdigest()


class ScheduledAdmission:
    def __init__(self, executions: ExecutionRepository, sessions: SessionStore) -> None:
        self._executions = executions
        self._sessions = sessions

    async def admit(
        self,
        definition: ProgramSchedule,
        context: ExecutionContext,
        prepared: PreparedExecution,
    ) -> ExecutionContext:
        if not definition.owner.owns(context.identity):
            raise PermissionError("Scheduled context does not belong to its owner")
        if not context.engine_handle:
            raise ValueError("Scheduled admission requires an accepted engine handle")
        execution_id = scheduled_execution_id(context.engine_handle)
        if (
            context.execution_id != execution_id
            or context.session_id != execution_id
            or context.root_execution_id != execution_id
            or context.parent_execution_id is not None
            or context.ancestor_execution_ids
        ):
            raise ValueError("Scheduled identities must be bound to the actual execution")
        session, inputs = stage_schedule(definition, context, context.credential_user_id())
        session.active_execution_id = execution_id
        session.active_inputs = definition.request.inputs
        session.execution_request = StartExecution(
            program=definition.request.session.program,
            inputs=inputs,
            execution_id=execution_id,
            session_id=session.run_id,
        )
        record = ExecutionRecord(
            execution_id=execution_id,
            owner=definition.owner,
            program=definition.request.session.program,
            inputs=inputs,
            context=session.run_context,
            location=prepared.location,
            session_id=session.run_id,
            phase=ExecutionPhase.RUNNING,
            submission=SubmissionState.ACCEPTED,
        )
        if not await self._executions.create(record, prepared):
            existing = await self._executions.get(execution_id)
            if request_digest(existing) != request_digest(record):
                raise ValueError("Scheduled execution identity already belongs to another request")
            session.run_context = existing.context
        # Execution acceptance precedes session admission, so reconciliation can
        # never submit a second engine run if this operation loses its reply.
        if not await self._sessions.create(session):
            existing_session = await self._sessions.get(session.run_id)
            if (
                not existing_session.identity.owns(definition.owner)
                or existing_session.active_execution_id != execution_id
                or existing_session.program != session.program
                or existing_session.metadata.schedule_id != definition.schedule_id
            ):
                raise SessionConflict("Scheduled session identity already belongs to another run")
        return session.run_context
