"""Application-owned recurring program policy over an external calendar service."""

import hashlib
import json
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import Field, JsonValue

from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.execution.models import PreparedExecution
from mas.execution.ports import ProgramExecutionPreparer
from mas.graph.state.graph_state import GraphState
from mas.programs.bindings import project
from mas.programs.models import Model
from mas.programs.service import ProgramService
from mas.scheduling.models import PromptSource, ScheduleDefinition, ScheduleStatus
from mas.session.domain.session_record import SessionRecord
from mas.session.execution.program_sessions import CreateProgramSession
from mas.session.execution.staging import stage_inputs


class CreateProgramSchedule(Model):
    session: CreateProgramSession
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    schedule: ScheduleDefinition
    source: PromptSource = PromptSource.MANUAL


class ProgramSchedule(Model):
    schedule_id: str = Field(min_length=1)
    owner: Identity
    request: CreateProgramSchedule
    version: int = Field(default=1, ge=1)


class ScheduleRegistration(Model):
    definition: ProgramSchedule
    prepared: PreparedExecution
    run_offset: int = Field(default=0, ge=0)


class ProgramScheduleView(Model):
    definition: ProgramSchedule
    status: ScheduleStatus
    remaining_actions: int | None = None
    total_runs: int = 0
    recent_runs: tuple[str, ...] = ()
    next_actions: tuple[datetime, ...] = ()


class ProgramScheduleError(RuntimeError):
    """Calendar transport failure with no provider diagnostics in public responses."""


class ProgramScheduleConflict(ValueError):
    """The caller must reload a changed schedule before updating it."""


class ProgramScheduleBackend(Protocol):
    async def create(self, registration: ScheduleRegistration) -> None: ...
    async def get(self, schedule_id: str, owner: Identity) -> ProgramScheduleView: ...
    async def list(self, owner: Identity, *, limit: int) -> list[ProgramScheduleView]: ...
    async def replace(
        self, registration: ScheduleRegistration, *, expected_version: int, restart: bool
    ) -> None: ...
    async def pause(self, schedule_id: str, *, paused: bool) -> None: ...
    async def trigger(self, schedule_id: str) -> None: ...
    async def delete(self, schedule_id: str) -> None: ...


class ProgramScheduleService:
    def __init__(
        self,
        programs: ProgramService,
        gateway: ProgramExecutionPreparer,
        backend: ProgramScheduleBackend,
    ) -> None:
        self._programs = programs
        self._gateway = gateway
        self._backend = backend

    async def _registration(
        self, definition: ProgramSchedule, credential_user_id: str
    ) -> ScheduleRegistration:
        # Use the same staging, contracts, and compiler as an interactive session.
        # The template is never submitted; a tick binds its actual private identity.
        template_handle = "schedule-template-" + definition.schedule_id
        context = ExecutionContext(
            identity=definition.owner,
            session_id="schedule-template-" + definition.schedule_id,
            engine_name="run_engine",
            engine_handle=template_handle,
        )
        staged, inputs = stage_schedule(definition, context, credential_user_id)
        if not staged.output_bindings.keys() <= GraphState.model_fields.keys():
            raise ValueError("Session output bindings target unknown graph state channels")
        revision = await self._programs.revision(
            definition.request.session.program, definition.owner
        )
        Draft202012Validator(revision.definition.input_schema).validate(inputs)
        prepared = await self._gateway.prepare(
            revision, inputs, staged.run_context, template_handle
        )
        return ScheduleRegistration(definition=definition, prepared=prepared)

    async def create(
        self,
        request: CreateProgramSchedule,
        caller: Identity,
        *,
        credential_user_id: str = "",
        request_key: str | None = None,
    ) -> ProgramScheduleView:
        request = CreateProgramSchedule.model_validate_json(request.model_dump_json())
        schedule_id = program_schedule_id(caller, request_key) if request_key else uuid4().hex
        if request_key is not None:
            if not 1 <= len(request_key) <= 256:
                raise ValueError("Schedule request key must contain between 1 and 256 characters")
            try:
                return await self._existing(schedule_id, request, caller)
            except KeyError:
                pass
        definition = ProgramSchedule(schedule_id=schedule_id, owner=caller, request=request)
        try:
            await self._backend.create(await self._registration(definition, credential_user_id))
        except ProgramScheduleConflict:
            if request_key is None:
                raise
            return await self._existing(schedule_id, request, caller)
        return await self.get(definition.schedule_id, caller)

    async def _existing(
        self, schedule_id: str, request: CreateProgramSchedule, caller: Identity
    ) -> ProgramScheduleView:
        view = await self.get(schedule_id, caller)
        if view.definition.request != request:
            raise ProgramScheduleConflict("Schedule request key belongs to a different request")
        return view

    async def get(self, schedule_id: str, caller: Identity) -> ProgramScheduleView:
        view = await self._backend.get(schedule_id, caller)
        if not view.definition.owner.owns(caller):
            raise PermissionError(schedule_id)
        return view

    async def list(self, caller: Identity, *, limit: int = 100) -> list[ProgramScheduleView]:
        if not 1 <= limit <= 100:
            raise ValueError("Schedule limit must be between 1 and 100")
        views = await self._backend.list(caller, limit=limit)
        return [view for view in views if view.definition.owner.owns(caller)]

    async def update(
        self,
        schedule_id: str,
        request: CreateProgramSchedule,
        caller: Identity,
        *,
        expected_version: int,
        credential_user_id: str = "",
    ) -> ProgramScheduleView:
        request = CreateProgramSchedule.model_validate_json(request.model_dump_json())
        view = await self.get(schedule_id, caller)
        current = view.definition
        if expected_version != current.version:
            raise ProgramScheduleConflict("Schedule changed; reload before updating")
        definition = ProgramSchedule(
            schedule_id=schedule_id,
            owner=current.owner,
            request=request,
            version=current.version + 1,
        )
        await self._backend.replace(
            await self._registration(definition, credential_user_id),
            expected_version=expected_version,
            restart=(
                view.status == ScheduleStatus.COMPLETED
                and current.request.schedule != request.schedule
            ),
        )
        return await self.get(schedule_id, caller)

    async def pause(
        self, schedule_id: str, caller: Identity, *, paused: bool
    ) -> ProgramScheduleView:
        await self.get(schedule_id, caller)
        await self._backend.pause(schedule_id, paused=paused)
        return await self.get(schedule_id, caller)

    async def trigger(self, schedule_id: str, caller: Identity) -> ProgramScheduleView:
        await self.get(schedule_id, caller)
        await self._backend.trigger(schedule_id)
        return await self.get(schedule_id, caller)

    async def delete(self, schedule_id: str, caller: Identity) -> None:
        await self.get(schedule_id, caller)
        await self._backend.delete(schedule_id)


def stage_schedule(
    definition: ProgramSchedule, context: ExecutionContext, credential_user_id: str
) -> tuple[SessionRecord, dict[str, JsonValue]]:
    request = definition.request
    session = request.session
    metadata = session.metadata.model_copy(deep=True)
    metadata.schedule_id = definition.schedule_id
    record = SessionRecord(
        run_id=context.session_id,
        identity=definition.owner,
        blueprint_id=session.blueprint_id,
        program=session.program,
        metadata=metadata,
        input_bindings=session.input_bindings,
        output_bindings=session.output_bindings,
        run_context=context,
    )
    stage_inputs(record, request.inputs, credential_user_id)
    inputs = {**project(record.input_bindings, record.graph_state.serialize()), **request.inputs}
    return record, inputs


def program_schedule_id(owner: Identity, request_key: str) -> str:
    data = json.dumps([owner.type.value, owner.id, request_key], ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()
