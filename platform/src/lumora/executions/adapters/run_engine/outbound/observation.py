"""Project recorded native coordination into safe application occurrence snapshots."""

import asyncio
from datetime import datetime

from pydantic import JsonValue
from runengine.coordination.models import RunRequest, RunStatus
from runengine.coordination.ports import CoordinationOperations, RunHandle
from runengine.coordination.targets import ExecutionTarget
from runengine.invocation.models import InvocationOutcome, InvocationRequest

from lumora.executions.domain.observation import OccurrenceKind, OccurrenceStatus
from lumora.executions.observation import OccurrenceProjection


class ObservedChild(RunHandle):
    def __init__(self, handle: RunHandle, owner: ObservedOperations, ordinal: int) -> None:
        self._handle, self._owner, self._ordinal = handle, owner, ordinal

    @property
    def run_id(self) -> str:
        return self._handle.run_id

    async def status(self) -> RunStatus:
        status = await self._handle.status()
        if status.phase in {"completed", "failed", "cancelled"}:
            await self._owner.finish(self._ordinal, OccurrenceStatus(status.phase.value))
        return status

    async def result(self, *, timeout: float | None = None) -> JsonValue:
        try:
            result = await self._handle.result(timeout=timeout)
        except BaseException:
            # A timeout/cancelled observer is not proof that its child terminated.
            await self.status()
            raise
        await self._owner.finish(self._ordinal, OccurrenceStatus.COMPLETED)
        return result

    async def cancel(self) -> None:
        await self._handle.cancel()
        await self.status()


class ObservedOperations:
    def __init__(
        self,
        operations: CoordinationOperations,
        execution_id: str,
        graph_sites: dict[str, OccurrenceKind] | None = None,
    ) -> None:
        self._operations = operations
        self._projection = OccurrenceProjection(execution_id)
        self._graph_sites = graph_sites
        self._active: dict[str, int] = {}
        self._positions: dict[str, tuple[int, int]] = {}

    @property
    def run_id(self) -> str:
        return self._operations.run_id

    async def initialize(self) -> None:
        await self._publish()

    async def _publish(self) -> None:
        await self._operations.publish_snapshot(
            {"lumora_observation": self._projection.snapshot().model_dump(mode="json")}
        )

    async def finish(self, ordinal: int, status: OccurrenceStatus) -> None:
        self._projection.finish(ordinal, status)
        await self._publish()

    async def execute(
        self, request: InvocationRequest, *, target: ExecutionTarget | None = None
    ) -> InvocationOutcome:
        site = request.metadata.get("lumora_call_site")
        node = request.kwargs.get("request_data")
        ordinal = (
            self._active.get(node.get("node_uid"))
            if self._graph_sites is not None and isinstance(node, dict)
            else None
        )
        if self._graph_sites is None and isinstance(site, str):
            kind = OccurrenceKind(request.metadata["lumora_call_kind"])
            ordinal = self._projection.start(site, kind)
            await self._publish()
        try:
            result = await self._operations.execute(request, target=target)
        except asyncio.CancelledError:
            if ordinal is not None:
                await self.finish(ordinal, OccurrenceStatus.CANCELLED)
            raise
        except Exception:
            if ordinal is not None:
                await self.finish(ordinal, OccurrenceStatus.FAILED)
            raise
        if ordinal is not None:
            await self.finish(
                ordinal, OccurrenceStatus.FAILED if result.failure else OccurrenceStatus.COMPLETED
            )
        return result

    async def invoke(
        self, request: InvocationRequest, *, target: ExecutionTarget | None = None
    ) -> JsonValue:
        return (await self.execute(request, target=target)).unwrap()

    async def start_child(
        self, request: RunRequest, *, key: str, environment_imports: dict[str, str] | None = None
    ) -> RunHandle:
        site = request.input.get("call_site") if isinstance(request.input, dict) else None
        if not isinstance(site, str):
            return await self._operations.start_child(
                request, key=key, environment_imports=environment_imports
            )
        ordinal = self._active.get(site) if self._graph_sites is not None else None
        if ordinal is None:
            ordinal = self._projection.start(site, OccurrenceKind.PROGRAM)
            await self._publish()
        try:
            handle = await self._operations.start_child(
                request, key=key, environment_imports=environment_imports
            )
        except asyncio.CancelledError:
            await self.finish(ordinal, OccurrenceStatus.CANCELLED)
            raise
        except Exception:
            await self.finish(ordinal, OccurrenceStatus.FAILED)
            raise
        self._projection.bind_child(ordinal, handle.run_id)
        await self._publish()
        return ObservedChild(handle, self, ordinal)

    def now(self) -> datetime:
        return self._operations.now()

    def random(self) -> float:
        return self._operations.random()

    async def sleep(self, seconds: float) -> None:
        await self._operations.sleep(seconds)

    async def receive(self, name: str, *, timeout: float | None = None) -> JsonValue:
        return await self._operations.receive(name, timeout=timeout)

    async def publish_snapshot(self, data: JsonValue) -> None:
        # Graph checkpoints remain native execution state. The outer Lumora run's
        # observation snapshot is its safe projection, not the work/state payload.
        await self._publish()

    async def publish_event(self, name: str, data: JsonValue) -> None:
        if self._graph_sites is not None and isinstance(data, dict):
            site = data.get("node_uid")
            if isinstance(site, str) and site in self._graph_sites:
                if name == "graph.node.started":
                    step = data.get("step", 0)
                    previous, attempts = self._positions.get(site, (-1, 0))
                    attempt = attempts + 1 if previous == step else 1
                    self._positions[site] = (step, attempt)
                    self._active[site] = self._projection.start(
                        site, self._graph_sites[site], graph_step=step, attempt=attempt
                    )
                elif site in self._active and name in {
                    "graph.node.completed",
                    "graph.node.failed",
                    "graph.node.retrying",
                }:
                    self._projection.finish(
                        self._active[site],
                        OccurrenceStatus.COMPLETED
                        if name == "graph.node.completed"
                        else OccurrenceStatus.FAILED,
                    )
                await self._publish()
        await self._operations.publish_event(name, data)
