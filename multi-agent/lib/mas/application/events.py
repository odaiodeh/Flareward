"""Authorize external delivery, then use the canonical root admission use case."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Annotated, Protocol, Self

from jsonschema import Draft202012Validator, SchemaError, ValidationError
from pydantic import (
    AfterValidator,
    AwareDatetime,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    model_validator,
)
from referencing import Registry
from referencing.exceptions import Unresolvable

from mas.application.access.consent import WorkflowConsentRequest, WorkflowConsents
from mas.application.access.credentials import OpaqueCredentials
from mas.application.execution.models import (
    AdmittedExecutionSettings,
    PreparedExecution,
    StartExecution,
)
from mas.application.execution.ports import ProgramExecutionPreparer
from mas.application.programs.interfaces import BindingContractError, InterfaceContract
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess, WorkflowAccessApproval
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.events import ProgramEvent, ProgramEventSource
from mas.domain.execution.models import ExecutionRecord, SubmissionState
from mas.domain.json_values import portable_json
from mas.domain.models import Model
from mas.domain.programs.models import ProgramRef, ProgramRevision


class EventAuthenticationError(PermissionError):
    """Delivery authority is absent, expired or revoked; never fall back to a cookie."""


class EventSourceUnavailable(RuntimeError):
    """Private registration could not be read or confirmed."""


class EventSourceConflict(ValueError):
    """The source changed or stopped accepting credential changes."""


class CreateEventSource(Model):
    model_config = ConfigDict(hide_input_in_errors=True)
    name: str = Field(min_length=1, max_length=200)
    program: ProgramRef
    event_type: str = Field(min_length=1, max_length=128)
    input_schema: Annotated[dict[str, JsonValue], AfterValidator(portable_json)] = Field(
        default_factory=dict
    )
    expires_at: AwareDatetime
    workflow_access: tuple[WorkflowAccess, ...] = Field(default=(), max_length=16)


class StoredEventSource(Model):
    model_config = ConfigDict(hide_input_in_errors=True)
    definition: ProgramEventSource
    prepared: PreparedExecution = Field(repr=False)
    secret_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)
    authorization_id: str | None = None
    credential_revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def bound_preparation(self) -> Self:
        if self.definition.prepared_sha256 != self.prepared.content_digest:
            raise ValueError("Event source preparation differs from its approved definition")
        if bool(self.definition.workflow_access) != bool(self.authorization_id):
            raise ValueError("Event source workflow consent is inconsistent")
        return self


@dataclass(frozen=True)
class IssuedEventSource:
    source: ProgramEventSource
    credential: SecretStr = field(repr=False)


class EventAdmission(Model):
    source_id: str
    event_id: str
    execution_id: str
    submission: SubmissionState


class EventSourceSettings(AdmittedExecutionSettings):
    credential_revision: int = Field(ge=0)


class RotateEventCredential(Model):
    expected_revision: int = Field(ge=0)


@dataclass(frozen=True)
class RotatedEventCredential:
    credential: SecretStr = field(repr=False)
    revision: int


class EventSourceStore(Protocol):
    async def create(self, registration: StoredEventSource) -> None: ...
    async def get(
        self, source_id: str, owner: Identity | None = None, *, active_at: datetime | None = None
    ) -> StoredEventSource: ...
    async def list(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[ProgramEventSource]: ...
    async def revoke(self, source_id: str, owner: Identity) -> None: ...
    async def rotate(
        self, source_id: str, owner: Identity, expected_revision: int, digest: str, *, now: datetime
    ) -> None: ...


class EventPrograms(Protocol):
    async def revision(self, reference: ProgramRef, caller: Identity) -> ProgramRevision: ...


class EventExecutions(Protocol):
    def approve_workflow_access(
        self, request: StartExecution, owner: Identity, approved_by: Identity | None
    ) -> WorkflowAccessApproval | None: ...
    async def start(
        self,
        request: StartExecution,
        caller: Identity,
        *,
        credential_user_id: str = "",
        context: ExecutionContext | None = None,
        workflow_access_approval: WorkflowAccessApproval | None = None,
        prepared_template: PreparedExecution | None = None,
    ) -> ExecutionRecord: ...


class ProgramEventService:
    def __init__(
        self,
        sources: EventSourceStore,
        programs: EventPrograms,
        executions: EventExecutions,
        preparer: ProgramExecutionPreparer,
        *,
        consents: WorkflowConsents | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sources, self._programs, self._executions = sources, programs, executions
        self._preparer, self._consents = preparer, consents
        self._now = clock or partial(datetime.now, UTC)
        self._credentials = OpaqueCredentials("unifai-event-v1")

    async def create(
        self, request: CreateEventSource, owner: Identity, approved_by: Identity
    ) -> IssuedEventSource:
        request = CreateEventSource.model_validate_json(request.model_dump_json())
        if (
            not approved_by.is_user
            or not approved_by.id
            or (owner.is_user and not owner.owns(approved_by))
        ):
            raise PermissionError("Event source creation requires authenticated human approval")
        try:
            InterfaceContract.check_schema(request.input_schema)
        except SchemaError, BindingContractError, RecursionError:
            raise ValueError("Event input schema must be a valid bundled interface") from None
        revision = await self._programs.revision(request.program, owner)
        issued = self._credentials.issue()
        context = ExecutionContext(identity=owner).with_credential_user(approved_by.id)
        prepared = await self._preparer.prepare(revision, {}, context, "")
        definition = ProgramEventSource(
            source_id=issued.identifier,
            owner=owner,
            approved_by=approved_by,
            approved_at=self._now(),
            prepared_sha256=prepared.content_digest,
            **request.model_dump(),
        )
        authorization_id = None
        if request.workflow_access:
            if self._consents is None:
                raise EventSourceUnavailable("Managed event workflow access is not configured")
            consent = await self._consents.approve(
                WorkflowConsentRequest(
                    requirements=request.workflow_access, expires_at=request.expires_at
                ),
                definition.source_id,
                definition.model_dump(mode="json"),
                prepared.content_digest,
                StartExecution(program=request.program, execution_id=definition.source_id),
                owner,
                approved_by,
            )
            authorization_id = consent.consent_id
        await self._sources.create(
            StoredEventSource(
                definition=definition,
                prepared=prepared,
                secret_sha256=issued.sha256,
                authorization_id=authorization_id,
            )
        )
        return IssuedEventSource(definition, issued.secret)

    async def get(self, source_id: str, owner: Identity) -> ProgramEventSource:
        return (await self._sources.get(source_id, owner)).definition

    async def settings(self, source_id: str, owner: Identity) -> EventSourceSettings:
        registration = await self._sources.get(source_id, owner)
        settings = AdmittedExecutionSettings.from_prepared(registration.prepared)
        return EventSourceSettings(
            **settings.model_dump(), credential_revision=registration.credential_revision
        )

    async def rotate(
        self, source_id: str, owner: Identity, request: RotateEventCredential
    ) -> RotatedEventCredential:
        issued = self._credentials.issue_for(source_id)
        await self._sources.rotate(
            source_id, owner, request.expected_revision, issued.sha256, now=self._now()
        )
        return RotatedEventCredential(issued.secret, request.expected_revision + 1)

    async def list(
        self, owner: Identity, *, after: str = "", limit: int = 100
    ) -> list[ProgramEventSource]:
        if not 1 <= limit <= 100:
            raise ValueError("Event source page size must be between 1 and 100")
        return await self._sources.list(owner, after=after, limit=limit)

    async def revoke(self, source_id: str, owner: Identity) -> None:
        await self._sources.revoke(source_id, owner)

    async def deliver(self, credential: str, event: ProgramEvent) -> EventAdmission:
        identifier = self._credentials.identify(credential)
        if identifier is None:
            raise EventAuthenticationError("Event delivery authentication required")
        try:
            registration = await self._sources.get(identifier, active_at=self._now())
        except KeyError:
            raise EventAuthenticationError("Event delivery authentication required") from None
        source = registration.definition
        if (
            source.revoked
            or source.expires_at <= self._now()
            or not self._credentials.matches(credential, registration.secret_sha256)
        ):
            raise EventAuthenticationError("Event delivery authentication required")
        event = ProgramEvent.model_validate_json(event.model_dump_json())
        if event.event_type != source.event_type:
            raise PermissionError("Event type is not permitted by this source")
        try:
            Draft202012Validator(source.input_schema, registry=Registry()).validate(event.inputs)
        except ValidationError, Unresolvable, RecursionError:
            raise ValueError("Event input violates its approved contract") from None
        public_id = (
            "event-"
            + hashlib.sha256(
                json.dumps([source.source_id, event.event_id], separators=(",", ":")).encode()
            ).hexdigest()
        )
        request = StartExecution(
            program=source.program,
            inputs=event.inputs,
            execution_id=public_id,
            workflow_access=source.workflow_access,
        )
        approval = None
        if source.workflow_access:
            if self._consents is None or registration.authorization_id is None:
                raise EventSourceUnavailable("Event workflow consent is unavailable")
            consent = await self._consents.resolve(
                registration.authorization_id,
                source.source_id,
                source.model_dump(mode="json"),
                registration.prepared.content_digest,
                source.owner,
            )
            approval = self._executions.approve_workflow_access(
                request, source.owner, consent.approved_by
            )
            if approval is None:
                raise EventSourceUnavailable("Event workflow consent is unavailable")
            approval = approval.model_copy(
                update={"approved_at": consent.approved_at, "consent_id": consent.consent_id}
            )
        record = await self._executions.start(
            request,
            source.owner,
            credential_user_id=source.approved_by.id,
            context=ExecutionContext(
                identity=source.owner,
                tags={
                    "event": {
                        "source_id": source.source_id,
                        "event_id": event.event_id,
                        "event_type": source.event_type,
                    }
                },
            ),
            workflow_access_approval=approval,
            prepared_template=registration.prepared,
        )
        return EventAdmission(
            source_id=source.source_id,
            event_id=event.event_id,
            execution_id=record.execution_id,
            submission=record.submission,
        )
