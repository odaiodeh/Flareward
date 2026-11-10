"""Reserve shared work before dispatch; delegate scheduling and all lifecycle to the host."""

import hashlib
import json
from datetime import datetime

from pydantic import JsonValue
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations, RunHandle
from runengine.coordination.targets import ExecutionTarget
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ThreadRunnerConfig
from runengine.invocation.errors import InvocationContractError
from runengine.invocation.models import InvocationOutcome, InvocationRequest

from lumora.executions.adapters.run_engine.shared.models import WorkBudgetBinding
from lumora.executions.budgets import WorkAdmission
from lumora.executions.domain.budgets import WorkBudget, WorkKind, WorkReservation
from lumora.executions.domain.context import ExecutionContext


class BudgetedOperations:
    def __init__(
        self,
        operations: CoordinationOperations,
        binding: WorkBudgetBinding,
        context: ExecutionContext,
        cancellation: FunctionRef | None = None,
    ) -> None:
        self._operations = operations
        self._binding = binding
        self._context = context
        self._budget = WorkBudget(
            root_execution_id=context.root_execution_id,
            owner=context.identity,
            limits=binding.limits,
        )
        self._dispatches = 0
        self._cancellation = cancellation

    async def initialize(self) -> None:
        if self._context.parent_execution_id is None:
            await self._admit(WorkAdmission(budget=self._budget))

    async def _admit(self, request: WorkAdmission) -> None:
        # Control-plane admission uses receiver-private storage settings, never the
        # selected sandbox/profile or a retained environment. It is journaled I/O.
        await self._operations.invoke(
            InvocationRequest(
                function=self._binding.admission,
                kwargs={"request": request.model_dump(mode="json")},
            ),
            target=ThreadRunnerConfig(),
        )

    async def _reserve(self, kind: WorkKind, key: str, data: JsonValue) -> None:
        fingerprint = hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        await self._admit(
            WorkAdmission(
                budget=self._budget,
                reservation=WorkReservation(
                    execution_id=self._context.execution_id,
                    key=key,
                    kind=kind,
                    depth=len(self._context.ancestor_execution_ids) + (kind == WorkKind.CHILD),
                    fingerprint=fingerprint,
                ),
            )
        )

    @property
    def run_id(self) -> str:
        return self._operations.run_id

    async def execute(
        self, request: InvocationRequest, *, target: ExecutionTarget | None = None
    ) -> InvocationOutcome:
        if self._cancellation is not None and request.function == self._cancellation:
            return await self._operations.execute(request, target=target)
        self._dispatches += 1
        try:
            await self._reserve(
                WorkKind.DISPATCH,
                f"dispatch-{self._dispatches}",
                {
                    "request": request.model_dump(mode="json"),
                    "target": target.model_dump(mode="json") if target is not None else None,
                },
            )
        except InvocationContractError as error:
            return InvocationOutcome.from_exception(error)
        return await self._operations.execute(request, target=target)

    async def invoke(
        self, request: InvocationRequest, *, target: ExecutionTarget | None = None
    ) -> JsonValue:
        return (await self.execute(request, target=target)).unwrap()

    async def start_child(
        self,
        request: RunRequest,
        *,
        key: str,
        environment_imports: dict[str, str] | None = None,
    ) -> RunHandle:
        await self._reserve(
            WorkKind.CHILD,
            key,
            {
                "request": request.model_dump(mode="json"),
                "imports": dict[str, JsonValue](environment_imports or {}),
            },
        )
        return await self._operations.start_child(
            request, key=key, environment_imports=environment_imports
        )

    def now(self) -> datetime:
        return self._operations.now()

    def random(self) -> float:
        return self._operations.random()

    async def sleep(self, seconds: float) -> None:
        await self._operations.sleep(seconds)

    async def receive(self, name: str, *, timeout: float | None = None) -> JsonValue:
        return await self._operations.receive(name, timeout=timeout)

    async def publish_snapshot(self, data: JsonValue) -> None:
        await self._operations.publish_snapshot(data)

    async def publish_event(self, name: str, data: JsonValue) -> None:
        await self._operations.publish_event(name, data)
