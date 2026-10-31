"""Program execution in existing sessions, with conditional turn lifecycle updates."""

import logging
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import Field, JsonValue, ValidationError

from mas.core.execution_context import ExecutionContext
from mas.core.hitl.models import ApprovalOverrides
from mas.core.identity import Identity
from mas.execution.models import TERMINAL_PHASES, ExecutionPhase, ExecutionRecord, StartExecution
from mas.execution.ports import ExecutionError
from mas.execution.service import ExecutionService
from mas.graph.state.graph_state import GraphState
from mas.interactions.models import parse_approval_rules
from mas.interactions.ports import ApprovalRulesPublisher
from mas.interactions.rules import ApprovalRuleChange
from mas.programs.bindings import BindingError, project
from mas.programs.models import Bindings, Model, ProgramRef
from mas.programs.service import ProgramService
from mas.session.domain.constants import CANCELLED_STATUS_MESSAGE, CANCELLED_TAG
from mas.session.domain.dto import SessionListFilter
from mas.session.domain.models import SessionMeta
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.execution.session_store import SessionConflict, SessionPage, SessionStore
from mas.session.execution.staging import stage_inputs

logger = logging.getLogger(__name__)
BUSY_STATUSES = frozenset(
    {
        SessionStatus.QUEUED,
        SessionStatus.RUNNING,
        SessionStatus.LOCKED,
        SessionStatus.IN_USE,
    }
)
PHASE_STATUS = {
    ExecutionPhase.SUBMITTING: SessionStatus.QUEUED,
    ExecutionPhase.UNKNOWN: SessionStatus.QUEUED,
    ExecutionPhase.RUNNING: SessionStatus.RUNNING,
    ExecutionPhase.COMPLETED: SessionStatus.COMPLETED,
    ExecutionPhase.FAILED: SessionStatus.FAILED,
    ExecutionPhase.CANCELLED: SessionStatus.CANCELLED,
}


class CreateProgramSession(Model):
    program: ProgramRef
    metadata: SessionMeta = Field(default_factory=SessionMeta)
    input_bindings: Bindings = Field(default_factory=dict)
    output_bindings: Bindings = Field(default_factory=dict)
    blueprint_id: str = ""


class StartSessionTurn(Model):
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    execution_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    scope: str = "public"


class ProgramSessionService:
    def __init__(
        self,
        store: SessionStore,
        programs: ProgramService,
        executions: ExecutionService,
        approval_rules: ApprovalRulesPublisher | None = None,
    ) -> None:
        self._store = store
        self._programs = programs
        self._executions = executions
        self._approval_rules = approval_rules
        self._reconcile_cursor: str | None = None

    async def create(self, request: CreateProgramSession, caller: Identity) -> SessionRecord:
        await self._programs.revision(request.program, caller)
        parse_approval_rules(getattr(request.metadata, "hitl_overrides", None))
        if not request.output_bindings.keys() <= GraphState.model_fields.keys():
            raise ValueError("Session output bindings target unknown graph state channels")
        session_id = str(uuid4())
        record = SessionRecord(
            run_id=session_id,
            identity=caller,
            blueprint_id=request.blueprint_id,
            program=request.program,
            metadata=request.metadata.model_copy(deep=True),
            input_bindings=request.input_bindings,
            output_bindings=request.output_bindings,
            run_context=ExecutionContext(session_id=session_id, identity=caller),
        )
        if not await self._store.create(record):
            raise SessionConflict("Session identity already exists")
        return record

    async def get(self, session_id: str, caller: Identity) -> SessionRecord:
        record = await self._store.get(session_id)
        if not record.identity.owns(caller):
            raise PermissionError(session_id)
        return record

    async def list(self, caller: Identity, *, limit: int = 100) -> list[SessionRecord]:
        return await self._store.list(caller, limit=limit)

    async def active_execution(
        self, session_id: str, caller: Identity, *, expected_id: str | None = None
    ) -> ExecutionRecord:
        record = await self.get(session_id, caller)
        if record.active_execution_id is None:
            raise KeyError("The session has no execution")
        if expected_id is not None and record.active_execution_id != expected_id:
            raise SessionConflict("The session has moved to another execution")
        execution = await self._executions.refresh(record.active_execution_id, caller)
        self._check_execution(record, execution)
        return execution

    @staticmethod
    def _check_execution(record: SessionRecord, execution: ExecutionRecord) -> None:
        if execution.session_id != record.run_id:
            raise SessionConflict("Execution identity belongs to another session")

    async def query(
        self, caller: Identity, filters: SessionListFilter, *, offset: int = 0, limit: int = 50
    ) -> SessionPage:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid session pagination")
        page = await self._store.query(caller, filters, offset=offset, limit=limit)
        return page.model_copy(
            update={
                "records": [await self.refresh(record.run_id, caller) for record in page.records]
            }
        )

    async def delete(self, session_id: str, caller: Identity) -> None:
        record = await self.refresh(session_id, caller)
        if record.status in BUSY_STATUSES:
            raise SessionConflict("Cancel the active execution before deleting its session")
        if not await self._store.delete(record):
            raise SessionConflict("Session changed concurrently; reload before retrying")

    async def scheduled(
        self, schedule_id: str, caller: Identity, *, limit: int = 20
    ) -> list[SessionRecord]:
        if not 1 <= limit <= 100:
            raise ValueError("Schedule history limit must be between 1 and 100")
        records = await self._store.scheduled(caller, schedule_id, limit=limit)
        return [await self.refresh(record.run_id, caller) for record in records]

    async def start(
        self,
        session_id: str,
        turn: StartSessionTurn,
        caller: Identity,
        *,
        credential_user_id: str = "",
    ) -> SessionRecord:
        record = await self.get(session_id, caller)
        if record.program is None:
            raise ValueError("Legacy session must be bound to a published program before execution")
        if self._same_turn(record, turn):
            return await self.refresh(session_id, caller)
        if record.status in BUSY_STATUSES:
            record = await self.refresh(session_id, caller)
            if self._same_turn(record, turn):
                return record
            if record.status in BUSY_STATUSES:
                raise SessionConflict("Session already has an active execution")
        try:
            await self._executions.get(turn.execution_id, caller)
        except KeyError:
            pass
        else:
            raise SessionConflict("Execution identity has already been used")
        staged = record.model_copy(deep=True)
        staged.run_context = staged.run_context.with_scope(turn.scope)
        stage_inputs(staged, turn.inputs, credential_user_id)
        inputs = {**project(staged.input_bindings, staged.graph_state.serialize()), **turn.inputs}
        revision = await self._programs.revision(record.program, caller)
        Draft202012Validator(revision.definition.input_schema).validate(inputs)
        staged.active_execution_id = turn.execution_id
        staged.active_inputs = turn.inputs
        staged.cancellation_requested = False
        staged.execution_request = StartExecution(
            program=record.program,
            inputs=inputs,
            execution_id=turn.execution_id,
            session_id=session_id,
        )
        try:
            await self._save(staged, record.version)
        except SessionConflict:
            latest = await self.get(session_id, caller)
            if not self._same_turn(latest, turn):
                raise
        return await self.refresh(session_id, caller)

    @staticmethod
    def _same_turn(record: SessionRecord, turn: StartSessionTurn) -> bool:
        if record.active_execution_id != turn.execution_id:
            return False
        if record.active_inputs != turn.inputs or record.run_context.scope != turn.scope:
            raise SessionConflict("Turn identity already belongs to a different request")
        return True

    async def _save(self, record: SessionRecord, expected_version: int) -> None:
        record.version = expected_version + 1
        if not await self._store.replace(record, expected_version=expected_version):
            raise SessionConflict("Session changed concurrently; reload before retrying")

    async def refresh(self, session_id: str, caller: Identity) -> SessionRecord:
        record = await self.get(session_id, caller)
        if record.status not in BUSY_STATUSES or record.execution_request is None:
            return record
        try:
            execution = await self._executions.get(record.active_execution_id, caller)
        except KeyError:
            if record.cancellation_requested:
                execution = await self._executions.prevent_start(
                    record.execution_request,
                    caller,
                    record.run_context,
                )
            else:
                try:
                    execution = await self._executions.start(
                        record.execution_request,
                        caller,
                        context=record.run_context,
                    )
                except ValueError:
                    record.status = SessionStatus.FAILED
                    record.run_context = record.run_context.mark_finished()
                    await self._save(record, record.version)
                    raise
        latest = await self.get(session_id, caller)
        self._check_execution(latest, execution)
        if latest.active_execution_id != execution.execution_id:
            return latest
        if latest.cancellation_requested and execution.phase not in TERMINAL_PHASES:
            await self._executions.cancel(execution.execution_id, caller)
        execution = await self._executions.refresh(execution.execution_id, caller)
        await self._publish_rules(latest, execution)
        return await self._project(session_id, execution)

    async def _publish_rules(self, record: SessionRecord, execution: ExecutionRecord) -> None:
        if (
            self._approval_rules is not None
            and record.approval_rules_revision
            and execution.phase not in TERMINAL_PHASES
        ):
            self._check_execution(record, execution)
            try:
                await self._approval_rules.save_rules(
                    execution.context.root_execution_id or execution.execution_id,
                    parse_approval_rules(getattr(record.metadata, "hitl_overrides", None)),
                    revision=record.approval_rules_revision,
                )
            except ExecutionError as error:
                raise ExecutionError(
                    error.failure.model_copy(
                        update={
                            "message": (
                                "Session approval policy is persisted; "
                                "live synchronization is pending"
                            ),
                            "code": "approval_rules_sync_pending",
                            "retryable": True,
                        }
                    )
                ) from error

    async def approval_rules(self, session_id: str, caller: Identity) -> ApprovalOverrides:
        record = await self.get(session_id, caller)
        return parse_approval_rules(getattr(record.metadata, "hitl_overrides", None))

    async def change_approval_rule(
        self, session_id: str, execution_id: str, change: ApprovalRuleChange, caller: Identity
    ) -> ApprovalOverrides:
        if self._approval_rules is None:
            raise SessionConflict("Approval rule publication is not configured")
        for _ in range(3):
            record = await self.get(session_id, caller)
            if record.active_execution_id != execution_id:
                raise SessionConflict("The session has moved to another execution")
            execution = await self._executions.refresh(execution_id, caller)
            self._check_execution(record, execution)
            if execution.phase in TERMINAL_PHASES:
                raise SessionConflict("The execution no longer accepts rule changes")
            rules = change.apply(
                parse_approval_rules(getattr(record.metadata, "hitl_overrides", None))
            )
            record.metadata = record.metadata.model_copy(
                update={"hitl_overrides": rules.to_dict()}, deep=True
            )
            record.approval_rules_revision = record.version + 1
            try:
                await self._save(record, record.version)
            except SessionConflict:
                # Reapply the pure command to fresh policy; no tool effects are retried.
                continue
            await self._publish_rules(record, execution)
            return rules
        raise SessionConflict("Approval rules changed concurrently; reload before retrying")

    async def _project(self, session_id: str, execution: ExecutionRecord) -> SessionRecord:
        # Always reload: network awaits can overlap a metadata edit or a newer turn.
        current = await self._store.get(session_id)
        if current.active_execution_id != execution.execution_id:
            return current
        if current.status not in BUSY_STATUSES:
            return current
        record = current.model_copy(deep=True)
        record.status = PHASE_STATUS[execution.phase]
        record.run_context = execution.context
        if execution.phase in TERMINAL_PHASES:
            record.run_context = record.run_context.mark_finished()
        if execution.phase == ExecutionPhase.COMPLETED:
            record.last_result = execution.result
            try:
                changes = project(record.output_bindings, execution.result)
                record.graph_state = GraphState.model_validate(
                    {**record.graph_state.serialize(), **changes}
                )
            except (BindingError, ValidationError) as error:
                record.status = SessionStatus.FAILED
                record.metadata.status_message = f"Session result binding failed: {error}"
        elif execution.phase == ExecutionPhase.CANCELLED:
            self._mark_cancelled(record)
        elif execution.phase == ExecutionPhase.FAILED and execution.failure:
            record.metadata.status_message = execution.failure.message
        if record == current:
            return current
        record.version = current.version + 1
        if not await self._store.replace(record, expected_version=current.version):
            return await self._store.get(session_id)
        return record

    @staticmethod
    def _mark_cancelled(record: SessionRecord) -> None:
        record.status = SessionStatus.CANCELLED
        record.run_context = record.run_context.mark_finished()
        record.metadata.tags[CANCELLED_TAG] = "true"
        record.metadata.status_message = CANCELLED_STATUS_MESSAGE
        if record.graph_state.messages:
            last = record.graph_state.messages[-1]
            record.graph_state.messages[-1] = last.model_copy(
                update={"metadata": {**last.metadata, "is_cancelled": True}}
            )

    async def cancel(self, session_id: str, caller: Identity) -> SessionRecord:
        record = await self.get(session_id, caller)
        if record.status not in BUSY_STATUSES:
            return record
        record.cancellation_requested = True
        await self._save(record, record.version)
        return await self.refresh(session_id, caller)

    async def update_metadata(
        self,
        session_id: str,
        metadata: SessionMeta,
        caller: Identity,
    ) -> SessionRecord:
        record = await self.get(session_id, caller)
        before = parse_approval_rules(getattr(record.metadata, "hitl_overrides", None))
        after = parse_approval_rules(getattr(metadata, "hitl_overrides", None))
        if before != after:
            record.approval_rules_revision = record.version + 1
        record.metadata = metadata.model_copy(deep=True)
        await self._save(record, record.version)
        if record.active_execution_id:
            try:
                execution = await self._executions.get(record.active_execution_id, caller)
            except KeyError:
                pass  # Admission intent is durable; refresh publishes after execution admission.
            else:
                await self._publish_rules(record, execution)
        return record

    async def reconcile_pending(self, *, limit: int = 100) -> None:
        records = await self._store.pending(limit=limit, after_session_id=self._reconcile_cursor)
        if not records and self._reconcile_cursor is not None:
            self._reconcile_cursor = None
            records = await self._store.pending(limit=limit)
        for record in records:
            self._reconcile_cursor = record.run_id
            try:
                await self.refresh(record.run_id, record.identity)
            except SessionConflict:
                # Another observer owns the newer version; inspect again next pass.
                continue
            except Exception:
                logger.exception("Session reconciliation failed for %s", record.run_id)
