"""Native calendar/process fixtures stay separate from schedule scenarios."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from mas.core.async_work import await_owned
from temporalio.client import (
    Client,
    DescribeScheduleInput,
    Interceptor,
    OutboundInterceptor,
    ScheduleActionExecutionStartWorkflow,
    ScheduleDescription,
    ScheduleHandle,
    WorkflowFailureError,
)
from temporalio.exceptions import is_cancelled_exception
from temporalio.service import RPCError, RPCStatusCode

from config.platform_settings import PlatformSettings
from config.worker_settings import WorkerSettings


class CalendarReadBarrier(Interceptor):
    """Hold two actual descriptions so their subsequent edits use one native token."""

    def __init__(self) -> None:
        self._barrier = asyncio.Barrier(2)

    def intercept_client(self, next: OutboundInterceptor) -> OutboundInterceptor:
        return CalendarReadFence(next, self._barrier)


class CalendarReadFence(OutboundInterceptor):
    def __init__(self, next: OutboundInterceptor, barrier: asyncio.Barrier) -> None:
        super().__init__(next)
        self._barrier = barrier
        self._reads = 0

    async def describe_schedule(self, input: DescribeScheduleInput) -> ScheduleDescription:
        description = await self.next.describe_schedule(input)
        self._reads += 1
        if self._reads <= 2:
            await self._barrier.wait()
        return description


@dataclass
class CalendarDeployment:
    settings: PlatformSettings
    worker: WorkerSettings
    native: Client
    schedule_ids: list[str] = field(default_factory=list)

    async def close_schedules(self) -> None:
        for schedule_id in self.schedule_ids:
            handle = self.native.get_schedule_handle("unifai-program-schedule-" + schedule_id)
            try:
                description = await handle.describe()
            except RPCError as error:
                if error.status == RPCStatusCode.NOT_FOUND:
                    continue
                raise
            await handle.delete()
            for action in description.info.running_actions:
                if not isinstance(action, ScheduleActionExecutionStartWorkflow):
                    continue
                run = self.native.get_workflow_handle(
                    action.workflow_id,
                    run_id=action.first_execution_run_id,
                    first_execution_run_id=action.first_execution_run_id,
                )
                await run.cancel()
                try:
                    await await_owned(run.result())
                except WorkflowFailureError as error:
                    if not is_cancelled_exception(error.cause):
                        raise


async def wait_schedule_runs(
    http: httpx.AsyncClient, schedule_id: str, count: int, *, terminal: bool = True
) -> list[dict]:
    async with asyncio.timeout(30):
        while True:
            response = await http.get(f"/api/program-schedules/{schedule_id}/runs")
            assert response.status_code == 200, response.text
            runs = response.json()
            if len(runs) >= count and (
                not terminal
                or all(run["status"] in {"COMPLETED", "FAILED", "CANCELLED"} for run in runs)
            ):
                return runs
            await asyncio.sleep(0.05)


async def wait_calendar(
    handle: ScheduleHandle, predicate: Callable[[ScheduleDescription], bool]
) -> ScheduleDescription:
    async with asyncio.timeout(30):
        while True:
            description = await handle.describe()
            if predicate(description):
                return description
            await asyncio.sleep(0.05)
