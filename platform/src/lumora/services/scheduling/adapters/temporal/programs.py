"""Temporal owns recurrence; each action starts the generic Run Engine workflow."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import ValidationError
from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.adapters.coordination.temporal.models import RunParameters, TemporalRunIdentity
from runengine.adapters.coordination.temporal.protocol import WORKFLOW_NAME
from runengine.coordination.models import RunRequest
from runengine.core.refs import FunctionRef
from temporalio.api.common.v1 import Payload
from temporalio.api.workflowservice.v1 import UpdateScheduleRequest
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionExecutionStartWorkflow,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleDescription,
    ScheduleIntervalSpec,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)
from temporalio.client import (
    ScheduleOverlapPolicy as NativeOverlap,
)
from temporalio.service import RPCError, RPCStatusCode

from lumora.executions.adapters.run_engine.inbound.schedules import execute_scheduled_program
from lumora.executions.adapters.run_engine.shared.scheduling import ScheduledProgramInput
from lumora.services.identity.domain import Identity
from lumora.services.scheduling.admission import scheduled_execution_id
from lumora.services.scheduling.models import ScheduleOverlapPolicy, ScheduleStatus
from lumora.services.scheduling.programs import (
    ProgramScheduleConflict,
    ProgramScheduleError,
    ProgramScheduleView,
    ScheduleRegistration,
)

_PREFIX = "lumora-program-schedule-"
_OWNER_MEMO = "lumora-program-schedule-owner"
_RPC_TIMEOUT = timedelta(seconds=10)
_OVERLAP = {
    ScheduleOverlapPolicy.SKIP: NativeOverlap.SKIP,
    ScheduleOverlapPolicy.BUFFER_ONE: NativeOverlap.BUFFER_ONE,
    ScheduleOverlapPolicy.CANCEL_OTHER: NativeOverlap.CANCEL_OTHER,
}


@asynccontextmanager
async def calendar_errors(schedule_id: str = "") -> AsyncIterator[None]:
    try:
        yield
    except ScheduleAlreadyRunningError as error:
        raise ProgramScheduleConflict("Schedule already exists") from error
    except RPCError as error:
        if error.status == RPCStatusCode.NOT_FOUND:
            raise KeyError(schedule_id) from error
        if error.status in {RPCStatusCode.ABORTED, RPCStatusCode.FAILED_PRECONDITION}:
            raise ProgramScheduleConflict("Schedule changed; reload before updating") from error
        if error.status == RPCStatusCode.INVALID_ARGUMENT:
            raise ValueError("Calendar service rejected the schedule configuration") from error
        raise ProgramScheduleError("Calendar service is unavailable") from error


class TemporalProgramSchedules:
    def __init__(
        self, host: TemporalHostConfig, admission: FunctionRef, *, client: Client | None = None
    ) -> None:
        if client is not None and client.namespace != host.namespace:
            raise ValueError("Schedule client namespace must match its execution host")
        admission.validate_portable()
        self._client = client
        self._host = host.model_copy(deep=True)
        self._admission = admission
        self._connection_lock = asyncio.Lock()

    async def _connect(self) -> Client:
        async with self._connection_lock:
            if self._client is None:
                try:
                    self._client = await Client.connect(
                        self._host.endpoint, namespace=self._host.namespace
                    )
                except (OSError, RuntimeError) as error:
                    raise ProgramScheduleError("Calendar service is unavailable") from error
            return self._client

    def _schedule(
        self,
        registration: ScheduleRegistration,
        *,
        consumed_actions: int = 0,
        paused: bool | None = None,
    ) -> Schedule:
        definition = registration.definition
        timing = definition.request.schedule
        template = RunRequest.model_validate_json(registration.prepared.payload_json)
        request = template.model_copy(
            update={
                "program": FunctionRef.from_callable(execute_scheduled_program),
                "run_id": "",
                "input": ScheduledProgramInput(
                    registration=registration, admission=self._admission
                ).model_dump(mode="json"),
            },
            deep=True,
        )
        parameters = RunParameters(
            request=request,
            invocation_timeout_seconds=self._host.invocation_timeout_seconds,
            invocation_heartbeat_timeout_seconds=self._host.invocation_heartbeat_timeout_seconds,
            delivery_max_attempts=self._host.delivery_max_attempts,
            message_delivery_timeout_seconds=self._host.message_delivery_timeout_seconds,
        )
        offset = (
            (timing.start_at - datetime(1970, 1, 1, tzinfo=UTC)) % timing.interval
            if timing.interval is not None and timing.start_at is not None
            else None
        )
        return Schedule(
            action=ScheduleActionStartWorkflow(
                WORKFLOW_NAME,
                parameters.model_dump(mode="json"),
                id="lumora-tick-" + definition.schedule_id,
                task_queue=self._host.task_queue,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timing.interval, offset=offset)]
                if timing.interval is not None
                else [],
                cron_expressions=[timing.cron_expression] if timing.cron_expression else [],
                time_zone_name=timing.timezone,
                start_at=timing.start_at,
                end_at=timing.end_at,
            ),
            policy=SchedulePolicy(overlap=_OVERLAP[timing.overlap_policy]),
            state=ScheduleState(
                paused=not timing.enabled if paused is None else paused,
                limited_actions=timing.remaining_actions is not None,
                remaining_actions=max(0, timing.remaining_actions - consumed_actions)
                if timing.remaining_actions is not None
                else 0,
            ),
        )

    async def _registration(self, description: ScheduleDescription) -> ScheduleRegistration:
        action = description.schedule.action
        if not isinstance(action, ScheduleActionStartWorkflow) or action.workflow != WORKFLOW_NAME:
            raise ProgramScheduleError("Stored schedule has an incompatible action")
        try:
            arguments = (
                await (await self._connect()).data_converter.decode(action.args)
                if action.args and isinstance(action.args[0], Payload)
                else action.args
            )
            parameters = RunParameters.model_validate(arguments[0])
            if (
                parameters.request.program.model_dump()
                != FunctionRef.from_callable(execute_scheduled_program).model_dump()
            ):
                raise ValueError("Incompatible scheduled program")
            return ScheduledProgramInput.model_validate(parameters.request.input).registration
        except (ValueError, IndexError, TypeError, ValidationError) as error:
            raise ProgramScheduleError("Stored schedule has an incompatible payload") from error

    async def _view(self, description: ScheduleDescription) -> ProgramScheduleView:
        registration = await self._registration(description)
        state, info = description.schedule.state, description.info
        timing = registration.definition.request.schedule
        complete = (state.limited_actions and state.remaining_actions == 0) or (
            timing.end_at is not None and timing.end_at <= datetime.now(UTC)
        )
        return ProgramScheduleView(
            definition=registration.definition,
            authorization_id=registration.authorization_id,
            status=ScheduleStatus.COMPLETED
            if complete
            else ScheduleStatus.PAUSED
            if state.paused
            else ScheduleStatus.ACTIVE,
            remaining_actions=state.remaining_actions if state.limited_actions else None,
            total_runs=max(0, info.num_actions - registration.run_offset),
            recent_runs=tuple(
                scheduled_execution_id(
                    TemporalRunIdentity(
                        namespace=self._host.namespace,
                        workflow_id=run.action.workflow_id,
                        run_id=run.action.first_execution_run_id,
                    ).encode()
                )
                for run in reversed(info.recent_actions)
                if isinstance(run.action, ScheduleActionExecutionStartWorkflow)
            ),
            next_actions=tuple(info.next_action_times),
        )

    async def create(self, registration: ScheduleRegistration) -> None:
        async with calendar_errors(registration.definition.schedule_id):
            await (await self._connect()).create_schedule(
                _PREFIX + registration.definition.schedule_id,
                self._schedule(registration),
                memo={_OWNER_MEMO: registration.definition.owner.model_dump(mode="json")},
                rpc_timeout=_RPC_TIMEOUT,
            )

    async def get(self, schedule_id: str, owner: Identity) -> ProgramScheduleView:
        async with calendar_errors(schedule_id):
            description = (
                await (await self._connect())
                .get_schedule_handle(_PREFIX + schedule_id)
                .describe(rpc_timeout=_RPC_TIMEOUT)
            )
            memo = await description.memo_value(_OWNER_MEMO, None)
            if memo is None or not Identity.model_validate(memo).owns(owner):
                raise PermissionError(schedule_id)
            return await self._view(description)

    async def registration(self, schedule_id: str, owner: Identity) -> ScheduleRegistration:
        async with calendar_errors(schedule_id):
            description = (
                await (await self._connect())
                .get_schedule_handle(_PREFIX + schedule_id)
                .describe(rpc_timeout=_RPC_TIMEOUT)
            )
            memo = await description.memo_value(_OWNER_MEMO, None)
            if memo is None or not Identity.model_validate(memo).owns(owner):
                raise PermissionError(schedule_id)
            return await self._registration(description)

    async def list(self, owner: Identity, *, limit: int) -> list[ProgramScheduleView]:
        result = []
        async with calendar_errors():
            async for item in await (await self._connect()).list_schedules(
                page_size=100, rpc_timeout=_RPC_TIMEOUT
            ):
                if not item.id.startswith(_PREFIX):
                    continue
                memo = await item.memo_value(_OWNER_MEMO, None)
                if memo is None or not Identity.model_validate(memo).owns(owner):
                    continue
                try:
                    result.append(await self.get(item.id.removeprefix(_PREFIX), owner))
                except KeyError:
                    continue
                if len(result) == limit:
                    break
        return result

    async def replace(
        self, registration: ScheduleRegistration, *, expected_version: int, restart: bool
    ) -> None:
        async with calendar_errors(registration.definition.schedule_id):
            client = await self._connect()
            native_id = _PREFIX + registration.definition.schedule_id
            current = await client.get_schedule_handle(native_id).describe(rpc_timeout=_RPC_TIMEOUT)
            previous = await self._registration(current)
            if previous.definition.version != expected_version:
                raise ProgramScheduleConflict("Schedule changed; reload before updating")
            if not previous.definition.owner.owns(registration.definition.owner):
                raise PermissionError(registration.definition.schedule_id)
            offset = current.info.num_actions if restart else previous.run_offset
            replacement = registration.model_copy(update={"run_offset": offset})
            previous_limit = previous.definition.request.schedule.remaining_actions
            consumed = (
                max(0, previous_limit - current.schedule.state.remaining_actions)
                if previous_limit is not None
                else current.info.num_actions - previous.run_offset
            )
            enabled = registration.definition.request.schedule.enabled
            paused = (
                current.schedule.state.paused
                if enabled == previous.definition.request.schedule.enabled
                else not enabled
            )
            replacement_schedule = self._schedule(
                replacement, consumed_actions=0 if restart else consumed, paused=paused
            )
            # SDK 1.35's handle.update omits the server's conflict token. Keep its
            # serialization here, then use the public fenced RPC.
            await client.workflow_service.update_schedule(
                UpdateScheduleRequest(
                    namespace=client.namespace,
                    schedule_id=native_id,
                    schedule=await replacement_schedule._to_proto(client),
                    conflict_token=current.raw_description.conflict_token,
                    identity=client.identity,
                    request_id=uuid4().hex,
                ),
                timeout=_RPC_TIMEOUT,
            )
            # The legacy schedule service acknowledges queueing the update; a
            # conflicting token can be rejected later inside its workflow.
            try:
                async with asyncio.timeout(_RPC_TIMEOUT.total_seconds()):
                    while True:
                        observed = await client.get_schedule_handle(native_id).describe(
                            rpc_timeout=_RPC_TIMEOUT
                        )
                        applied = await self._registration(observed)
                        if applied.definition.version > expected_version:
                            if applied.model_dump(mode="json") == replacement.model_dump(
                                mode="json"
                            ):
                                return
                            raise ProgramScheduleConflict("Another schedule update was applied")
                        if (
                            observed.raw_description.conflict_token
                            != current.raw_description.conflict_token
                        ):
                            raise ProgramScheduleConflict(
                                "Schedule changed before the update applied"
                            )
                        await asyncio.sleep(0.05)
            except TimeoutError as error:
                raise ProgramScheduleError("Schedule update confirmation is unavailable") from error

    async def pause(self, schedule_id: str, *, paused: bool) -> None:
        async with calendar_errors(schedule_id):
            handle = (await self._connect()).get_schedule_handle(_PREFIX + schedule_id)
            await (handle.pause if paused else handle.unpause)(rpc_timeout=_RPC_TIMEOUT)
            try:
                async with asyncio.timeout(_RPC_TIMEOUT.total_seconds()):
                    while (
                        await handle.describe(rpc_timeout=_RPC_TIMEOUT)
                    ).schedule.state.paused != paused:
                        await asyncio.sleep(0.05)
            except TimeoutError as error:
                raise ProgramScheduleError("Schedule pause confirmation is unavailable") from error

    async def trigger(self, schedule_id: str) -> None:
        async with calendar_errors(schedule_id):
            await (
                (await self._connect())
                .get_schedule_handle(_PREFIX + schedule_id)
                .trigger(rpc_timeout=_RPC_TIMEOUT)
            )

    async def delete(self, schedule_id: str) -> None:
        async with calendar_errors(schedule_id):
            await (
                (await self._connect())
                .get_schedule_handle(_PREFIX + schedule_id)
                .delete(rpc_timeout=_RPC_TIMEOUT)
            )
