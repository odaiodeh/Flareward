"""Translate prepared requests, generic handles, and errors at the application boundary."""

from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import uuid4

from pydantic import JsonValue, ValidationError
from runengine.coordination.enums import RunFailureCode
from runengine.coordination.errors import RunContractError, RunSubmissionError
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import (
    MessageHandle,
    RunChildrenSource,
    RunEventSource,
    RunHandle,
    RunHost,
)
from runengine.invocation.errors import (
    InvocationContractError,
    InvocationInfrastructureError,
)

from lumora.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from lumora.executions.adapters.run_engine.outbound.errors import engine_errors, portable_failure
from lumora.executions.adapters.run_engine.outbound.profiles import placement_catalog
from lumora.executions.adapters.run_engine.outbound.status import execution_phase
from lumora.executions.adapters.run_engine.shared.context import current_context
from lumora.executions.adapters.run_engine.shared.models import ProgramPayload
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionPhase, ExecutionRecord, SubmissionState
from lumora.executions.models import PreparedExecution
from lumora.executions.ports import (
    ExecutionError,
    ExecutionLocationUnavailable,
    SubmissionUnconfirmed,
)
from lumora.programs.domain.models import ProgramRevision

PREPARED_FORMAT = "runengine/request-v10"


class RunEngineGateway:
    def __init__(
        self,
        host: RunHost,
        compiler: ProgramCompiler,
        *,
        location: str | None = None,
        handles: Callable[[str], Awaitable[RunHandle]] | None = None,
    ) -> None:
        self._host = host
        self._compiler = compiler
        self._location = location or "runengine:instance:" + uuid4().hex
        self._handle = handles or host.get_handle

    @property
    def location(self) -> str:
        return self._location

    async def prepare(
        self,
        revision: ProgramRevision,
        inputs: JsonValue,
        context: ExecutionContext,
        execution_id: str,
    ) -> PreparedExecution:
        request = await self._compiler.compile(revision, context.identity, context)
        payload = ProgramPayload.model_validate(request.input)
        payload.inputs = inputs
        request = request.model_copy(
            update={"input": payload.model_dump(mode="json"), "run_id": execution_id}, deep=True
        )
        request = self._host.validate(request)
        return PreparedExecution(
            format=PREPARED_FORMAT,
            payload_json=request.model_dump_json(),
            location=self.location,
            work_limits=payload.work_budget.limits if payload.work_budget is not None else None,
            admitted_profiles=placement_catalog(payload.placement),
            placement=payload.placement.summary,
        )

    def _request(self, prepared: PreparedExecution) -> RunRequest:
        if not prepared.location or prepared.location != self.location:
            raise ExecutionLocationUnavailable()
        if prepared.format != PREPARED_FORMAT:
            raise ValueError("Unsupported prepared execution format")
        try:
            prepared = PreparedExecution.model_validate_json(prepared.model_dump_json())
            request = RunRequest.model_validate_json(prepared.payload_json)
            payload = ProgramPayload.model_validate(request.input)
        except ValidationError:
            raise ValueError("Prepared execution snapshot is invalid") from None
        limits = payload.work_budget.limits if payload.work_budget is not None else None
        if limits != prepared.work_limits:
            raise ValueError("Prepared work limits differ from the admitted request")
        if placement_catalog(payload.placement) != prepared.admitted_profiles:
            raise ValueError("Prepared profiles differ from the admitted request")
        if payload.placement.summary is None or payload.placement.summary != prepared.placement:
            raise ValueError("Prepared placement differs from the admitted request")
        return request

    async def start(self, prepared: PreparedExecution, *, recover: bool = False) -> None:
        request = self._request(prepared)
        try:
            await self._host.start(request)
        except RunSubmissionError as error:
            raise SubmissionUnconfirmed(portable_failure(error)) from error
        except RunContractError as error:
            if recover and error.code == RunFailureCode.ALREADY_EXISTS:
                # Only application-owned private IDs with a recorded prior attempt use this path.
                return
            raise ExecutionError(portable_failure(error)) from error
        except (InvocationContractError, InvocationInfrastructureError) as error:
            raise ExecutionError(portable_failure(error)) from error

    async def bind(
        self,
        template: PreparedExecution,
        revision: ProgramRevision,
        inputs: JsonValue,
        context: ExecutionContext,
        execution_id: str,
    ) -> PreparedExecution:
        request = self._request(template)
        payload = ProgramPayload.model_validate(request.input)
        if (
            payload.program != revision.reference
            or payload.content_digest != revision.content_digest
            or not payload.context.identity.owns(context.identity)
        ):
            raise PermissionError("Execution template does not belong to this Program and owner")
        self._compiler.authorize_template(payload, context.identity)
        payload = payload.model_copy(update={"inputs": inputs, "context": context}, deep=True)
        request = self._host.validate(
            request.model_copy(
                update={"input": payload.model_dump(mode="json"), "run_id": execution_id}, deep=True
            )
        )
        return PreparedExecution(
            format=template.format,
            location=template.location,
            payload_json=request.model_dump_json(),
            work_limits=template.work_limits,
            admitted_profiles=template.admitted_profiles,
            placement=template.placement,
        )

    async def status(self, execution_id: str) -> ExecutionPhase:
        async with engine_errors():
            status = await (await self._handle(execution_id)).status()
        return execution_phase(status.phase)

    async def result(self, execution_id: str) -> JsonValue:
        async with engine_errors():
            return await (await self._handle(execution_id)).result()

    async def cancel(self, execution_id: str) -> None:
        async with engine_errors():
            await (await self._handle(execution_id)).cancel()

    async def send(self, execution_id: str, name: str, data: JsonValue) -> None:
        async with engine_errors():
            handle = await self._handle(execution_id)
            if not isinstance(handle, MessageHandle):
                raise ValueError("Execution host does not support messages")
            await handle.send(name, data)

    async def children(self, execution_id: str) -> list[ExecutionRecord]:
        async with engine_errors():
            handle = await self._handle(execution_id)
            if not isinstance(handle, RunChildrenSource):
                raise ValueError("Execution host does not support child observations")
            requests = await handle.children()
        records = []
        for request in requests:
            if request.parent_run_id != execution_id:
                raise ValueError("Observed child belongs to another parent run")
            payload = ProgramPayload.model_validate(request.input)
            context = current_context(payload.context, request.run_id)
            records.append(
                ExecutionRecord(
                    execution_id=context.execution_id,
                    owner=context.identity,
                    program=payload.program,
                    body_path=payload.body_path,
                    content_digest=payload.content_digest,
                    inputs=payload.inputs,
                    context=context,
                    admitted_profiles=placement_catalog(payload.placement),
                    location=self.location,
                    work_limits=payload.work_budget.limits
                    if payload.work_budget is not None
                    else None,
                    session_id=context.session_id or None,
                    parent_execution_id=context.parent_execution_id,
                    phase=ExecutionPhase.RUNNING,
                    submission=SubmissionState.ACCEPTED,
                )
            )
        return records

    async def events(self, execution_id: str, after_sequence: int = 0) -> AsyncIterator[JsonValue]:
        async with engine_errors():
            handle = await self._handle(execution_id)
            if not isinstance(handle, RunEventSource):
                raise ValueError("Execution host does not support observations")
            async for event in handle.events(after_sequence=after_sequence):
                yield event.model_dump(mode="json")

    async def close(self) -> None:
        await self._host.shutdown()
