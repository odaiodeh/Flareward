"""Translate prepared requests, generic handles, and errors at the application boundary."""

from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import uuid4

from mas.core.execution_context import ExecutionContext
from mas.execution.models import ExecutionPhase, ExecutionRecord, PreparedExecution, SubmissionState
from mas.execution.ports import ExecutionError, ExecutionLocationUnavailable, SubmissionUnconfirmed
from mas.programs.models import ProgramRevision
from pydantic import JsonValue
from run_engine.context import current_context
from run_engine.models import ProgramPayload
from runengine.coordination.enums import RunFailureCode, RunPhase
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

from outbound.run_engine.compiler import ProgramCompiler
from outbound.run_engine.errors import engine_errors, portable_failure

PREPARED_FORMAT = "runengine/request-v2"


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
        data = dict(request.input)
        data["inputs"] = inputs
        request = request.model_copy(update={"input": data, "run_id": execution_id}, deep=True)
        request = self._host.validate(request)
        return PreparedExecution(
            format=PREPARED_FORMAT, payload_json=request.model_dump_json(), location=self.location
        )

    async def start(self, prepared: PreparedExecution, *, recover: bool = False) -> None:
        prepared = PreparedExecution.model_validate_json(prepared.model_dump_json())
        if not prepared.location or prepared.location != self.location:
            raise ExecutionLocationUnavailable()
        if prepared.format != PREPARED_FORMAT:
            raise ValueError(f"Unsupported prepared execution format: {prepared.format}")
        request = RunRequest.model_validate_json(prepared.payload_json)
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

    async def status(self, execution_id: str) -> ExecutionPhase:
        async with engine_errors():
            status = await (await self._handle(execution_id)).status()
        return {
            RunPhase.RUNNING: ExecutionPhase.RUNNING,
            RunPhase.COMPLETED: ExecutionPhase.COMPLETED,
            RunPhase.FAILED: ExecutionPhase.FAILED,
            RunPhase.CANCELLED: ExecutionPhase.CANCELLED,
            RunPhase.UNKNOWN: ExecutionPhase.UNKNOWN,
        }[status.phase]

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
                    program=payload.revision.reference,
                    inputs=payload.inputs,
                    context=context,
                    location=self.location,
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
