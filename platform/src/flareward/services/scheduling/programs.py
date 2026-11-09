"""Application-owned recurring program policy over an external calendar service."""

import hashlib
import json
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import Field, JsonValue

from flareward.executions.domain.consent import WorkflowConsent
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.models import PreparedExecution, StartExecution
from flareward.executions.ports import ProgramExecutionPreparer
from flareward.models import Model
from flareward.programs.domain.bindings import project
from flareward.programs.service import ProgramService
from flareward.services.access.consent import (
    WorkflowConsentRequest,
    WorkflowConsents,
    consent_definition_digest,
)
from flareward.services.access.credentials import WorkflowCredentialUnavailable
from flareward.services.identity.domain import Identity
from flareward.services.scheduling.models import PromptSource, ScheduleDefinition, ScheduleStatus
from flareward.services.sessions.execution.program_sessions import CreateProgramSession
from flareward.services.sessions.execution.projection import SessionProjection
from flareward.services.sessions.execution.staging import stage_inputs
from flareward.services.sessions.records import SessionRecord


class CreateProgramSchedule(Model):
    session: CreateProgramSession
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    schedule: ScheduleDefinition
    source: PromptSource = PromptSource.MANUAL
    workflow_access: WorkflowConsentRequest | None = None


class ProgramSchedule(Model):
    schedule_id: str = Field(min_length=1)
    owner: Identity
    request: CreateProgramSchedule
    version: int = Field(default=1, ge=1)


class ScheduleRegistration(Model):
    definition: ProgramSchedule
    prepared: PreparedExecution
    run_offset: int = Field(default=0, ge=0)
    authorization_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class ProgramScheduleView(Model):
    definition: ProgramSchedule
    status: ScheduleStatus
    remaining_actions: int | None = None
    total_runs: int = 0
    recent_runs: tuple[str, ...] = ()
    next_actions: tuple[datetime, ...] = ()
    authorization_id: str | None = None
    workflow_access_consent: WorkflowConsent | None = None


class ProgramScheduleError(RuntimeError):
    """Calendar transport failure with no provider diagnostics in public responses."""


class ProgramScheduleConflict(ValueError):
    """The caller must reload a changed schedule before updating it."""


class AppliedScheduleReader(Protocol):
    async def registration(self, schedule_id: str, owner: Identity) -> ScheduleRegistration: ...


class ProgramScheduleBackend(AppliedScheduleReader, Protocol):
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
        consents: WorkflowConsents | None = None,
    ) -> None:
        self._programs = programs
        self._gateway = gateway
        self._backend = backend
        self._consents = consents

    async def _registration(
        self,
        definition: ProgramSchedule,
        credential_user_id: str,
        approved_by: Identity | None = None,
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
        SessionProjection.validate(staged.interaction, set(staged.output_bindings))
        revision = await self._programs.revision(
            definition.request.session.program, definition.owner
        )
        Draft202012Validator(revision.definition.input_schema).validate(inputs)
        prepared = await self._gateway.prepare(
            revision, inputs, staged.run_context, template_handle
        )
        registration = ScheduleRegistration(definition=definition, prepared=prepared)
        if definition.request.workflow_access is not None:
            if approved_by is None:
                raise PermissionError(
                    "Schedule workflow access requires authenticated human consent"
                )
            if self._consents is None:
                raise WorkflowCredentialUnavailable("Scheduled workflow consent is not configured")
            consent = await self._consents.approve(
                definition.request.workflow_access,
                definition.schedule_id,
                definition.model_dump(mode="json"),
                prepared.content_digest,
                StartExecution(
                    program=definition.request.session.program,
                    inputs=inputs,
                    execution_id=template_handle,
                    session_id=context.session_id,
                ),
                definition.owner,
                approved_by,
            )
            registration = registration.model_copy(update={"authorization_id": consent.consent_id})
        return registration

    async def create(
        self,
        request: CreateProgramSchedule,
        caller: Identity,
        *,
        credential_user_id: str = "",
        request_key: str | None = None,
        approved_by: Identity | None = None,
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
            await self._backend.create(
                await self._registration(definition, credential_user_id, approved_by)
            )
        except ProgramScheduleConflict:
            if request_key is None:
                raise
            return await self._existing(schedule_id, request, caller)
        return await self.get(definition.schedule_id, caller)

    async def _existing(
        self, schedule_id: str, request: CreateProgramSchedule, caller: Identity
    ) -> ProgramScheduleView:
        view = await self.get(schedule_id, caller)
        if consent_definition_digest(
            view.definition.request.model_dump(mode="json")
        ) != consent_definition_digest(request.model_dump(mode="json")):
            raise ProgramScheduleConflict("Schedule request key belongs to a different request")
        return view

    async def get(self, schedule_id: str, caller: Identity) -> ProgramScheduleView:
        view = await self._backend.get(schedule_id, caller)
        if not view.definition.owner.owns(caller):
            raise PermissionError(schedule_id)
        return await self._consent_view(view, caller)

    async def _consent_view(
        self, view: ProgramScheduleView, caller: Identity
    ) -> ProgramScheduleView:
        if view.definition.request.workflow_access is None and view.authorization_id is None:
            return view
        if (
            self._consents is None
            or view.authorization_id is None
            or view.definition.request.workflow_access is None
        ):
            raise WorkflowCredentialUnavailable("Scheduled workflow consent is unavailable")
        consent = await self._consents.get(view.authorization_id, caller)
        if (
            consent.definition_sha256
            != consent_definition_digest(view.definition.model_dump(mode="json"))
            or consent.source_id != view.definition.schedule_id
        ):
            raise WorkflowCredentialUnavailable(
                "Schedule consent metadata does not match its definition"
            )
        return view.model_copy(update={"workflow_access_consent": consent})

    async def list(self, caller: Identity, *, limit: int = 100) -> list[ProgramScheduleView]:
        if not 1 <= limit <= 100:
            raise ValueError("Schedule limit must be between 1 and 100")
        views = await self._backend.list(caller, limit=limit)
        return [
            await self._consent_view(view, caller)
            for view in views
            if view.definition.owner.owns(caller)
        ]

    async def update(
        self,
        schedule_id: str,
        request: CreateProgramSchedule,
        caller: Identity,
        *,
        expected_version: int,
        credential_user_id: str = "",
        approved_by: Identity | None = None,
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
            await self._registration(definition, credential_user_id, approved_by),
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
        view = await self.get(schedule_id, caller)
        if view.definition.request.workflow_access is not None:
            if self._consents is None or view.authorization_id is None:
                raise WorkflowCredentialUnavailable("Scheduled workflow consent is unavailable")
            current = await self._backend.registration(schedule_id, caller)
            await self._consents.resolve(
                view.authorization_id,
                schedule_id,
                current.definition.model_dump(mode="json"),
                current.prepared.content_digest,
                caller,
            )
        await self._backend.trigger(schedule_id)
        return await self.get(schedule_id, caller)

    async def delete(self, schedule_id: str, caller: Identity) -> None:
        # Removal remains available if optional consent metadata cannot be read.
        view = await self._backend.get(schedule_id, caller)
        if not view.definition.owner.owns(caller):
            raise PermissionError(schedule_id)
        await self._backend.delete(schedule_id)

    async def revoke_workflow_access(self, schedule_id: str, caller: Identity) -> None:
        view = await self.get(schedule_id, caller)
        if self._consents is None or view.authorization_id is None:
            raise ValueError("Schedule has no managed workflow consent")
        await self._consents.revoke(view.authorization_id, caller)


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
        interaction=session.interaction,
        metadata=metadata,
        input_bindings=session.input_bindings,
        output_bindings=session.output_bindings,
        run_context=context,
    )
    stage_inputs(record, request.inputs, credential_user_id)
    inputs = {**project(record.input_bindings, SessionProjection.source(record)), **request.inputs}
    return record, inputs


def program_schedule_id(owner: Identity, request_key: str) -> str:
    data = json.dumps([owner.type.value, owner.id, request_key], ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()
