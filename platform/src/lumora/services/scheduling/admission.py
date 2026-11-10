"""Idempotent business-record admission for an already started scheduled run."""

import hashlib

from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.identity import request_digest
from lumora.executions.domain.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    SubmissionState,
)
from lumora.executions.models import PreparedExecution, StartExecution
from lumora.executions.ports import ExecutionRepository
from lumora.services.access.admission import WorkflowAccessAdmission, check_access_approval
from lumora.services.access.consent import WorkflowConsents
from lumora.services.access.credentials import WorkflowCredentialUnavailable
from lumora.services.scheduling.programs import (
    AppliedScheduleReader,
    ProgramSchedule,
    ScheduleRegistration,
    stage_schedule,
)
from lumora.services.sessions.execution.session_store import SessionConflict, SessionStore


def scheduled_execution_id(native_id: str) -> str:
    return "scheduled-" + hashlib.sha256(native_id.encode()).hexdigest()


class ScheduledAdmission:
    def __init__(
        self,
        executions: ExecutionRepository,
        sessions: SessionStore,
        *,
        consents: WorkflowConsents | None = None,
        workflow_access: WorkflowAccessAdmission | None = None,
        calendar: AppliedScheduleReader | None = None,
    ) -> None:
        self._executions = executions
        self._sessions = sessions
        self._consents, self._workflow_access, self._calendar = consents, workflow_access, calendar

    async def admit(
        self,
        definition: ProgramSchedule,
        context: ExecutionContext,
        prepared: PreparedExecution,
        *,
        registration: ScheduleRegistration | None = None,
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
            workflow_access=definition.request.workflow_access.requirements
            if definition.request.workflow_access is not None
            else (),
        )
        approval = None
        if definition.request.workflow_access is not None:
            if (
                self._consents is None
                or self._workflow_access is None
                or self._calendar is None
                or registration is None
                or registration.authorization_id is None
                or registration.definition != definition
            ):
                raise WorkflowCredentialUnavailable("Scheduled workflow consent is unavailable")
            current = await self._calendar.registration(definition.schedule_id, definition.owner)
            if (
                current.definition != definition
                or current.authorization_id != registration.authorization_id
                or current.prepared.content_digest != registration.prepared.content_digest
            ):
                raise PermissionError("Schedule registration was superseded")
            consent = await self._consents.resolve(
                registration.authorization_id,
                definition.schedule_id,
                definition.model_dump(mode="json"),
                registration.prepared.content_digest,
                definition.owner,
            )
            approval = self._workflow_access.approve(
                session.execution_request, definition.owner, consent.approved_by
            ).model_copy(
                update={"approved_at": consent.approved_at, "consent_id": consent.consent_id}
            )
            check_access_approval(session.execution_request, definition.owner, approval)
        elif registration is not None and registration.authorization_id is not None:
            raise PermissionError("Unexpected schedule workflow consent")
        session.workflow_access_approval = approval
        record = ExecutionRecord(
            execution_id=execution_id,
            owner=definition.owner,
            program=definition.request.session.program,
            inputs=inputs,
            context=session.run_context,
            location=prepared.location,
            work_limits=prepared.work_limits,
            admitted_profiles=prepared.admitted_profiles,
            workflow_access_approval=approval,
            session_id=session.run_id,
            phase=ExecutionPhase.RUNNING,
            submission=SubmissionState.ACCEPTED,
        )
        if not await self._executions.create(record, prepared):
            existing = await self._executions.get(execution_id)
            if request_digest(existing) != request_digest(record):
                raise ValueError("Scheduled execution identity already belongs to another request")
            session.run_context = existing.context
            record = existing
        if (
            approval is not None
            and record.phase not in TERMINAL_PHASES
            and not record.cancel_requested
        ):
            assert self._workflow_access is not None
            await self._workflow_access.provision(record)
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
