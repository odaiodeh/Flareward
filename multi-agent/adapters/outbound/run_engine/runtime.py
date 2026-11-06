"""Application runtime operations implemented with engine primitives."""

from collections.abc import Awaitable, Callable
from functools import partial

from inbound.run_engine.elements import invoke_element
from mas.application.execution.placement import PlacementRefused
from mas.core.enums import ResourceCategory
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution_preferences import ExecutionSelection
from mas.graph.models.step_context import StepContext
from pydantic import JsonValue
from run_engine.context import child_request
from run_engine.models import ElementCall, ElementSpecifications, ProgramPlacement
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations, RunHandle
from runengine.coordination.targets import EnvironmentTarget
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ExecutorConfig
from runengine.invocation.models import InvocationRequest

from outbound.run_engine.errors import engine_errors


class ChildProgramExecution:
    def __init__(
        self, handle: RunHandle, cancel_waits: Callable[[], Awaitable[None]] | None = None
    ) -> None:
        self._handle = handle
        self._cancel_waits = cancel_waits

    @property
    def execution_id(self) -> str:
        return self._handle.run_id

    async def result(self) -> JsonValue:
        async with engine_errors():
            return await self._handle.result()

    async def cancel(self) -> None:
        async with engine_errors():
            try:
                if self._cancel_waits is not None:
                    await self._cancel_waits()
            finally:
                await self._handle.cancel()


class RunEngineProgramRuntime:
    def __init__(
        self,
        operations: CoordinationOperations,
        children: dict[str, dict[str, JsonValue]],
        specifications: ElementSpecifications,
        context: ExecutionContext,
        placement: ProgramPlacement,
        receiver: FunctionRef | None = None,
        cancellation: FunctionRef | None = None,
    ) -> None:
        self._operations = operations
        self._children = children
        self._specifications = specifications
        self._context = context
        self._receiver = receiver
        self._cancellation = cancellation
        self._placement = placement.model_copy(deep=True)
        self._profiles = {
            name: ExecutorConfig.model_validate(target)
            for name, target in placement.profiles.items()
        }
        self._element_target = self._target(None)

    def _target(self, selection: ExecutionSelection | None) -> ExecutorConfig | EnvironmentTarget:
        selection = ExecutionSelection.model_validate(selection.model_dump() if selection else {})
        if selection.environment is not None:
            if selection.environment not in self._placement.environments:
                raise PlacementRefused("Invocation references an undeclared environment")
            return EnvironmentTarget(name=selection.environment)
        profile = selection.profile or self._placement.default_profile
        if profile not in self._profiles:
            raise PlacementRefused("Invocation profile is not approved")
        return self._profiles[profile].model_copy(deep=True)

    @property
    def execution_id(self) -> str:
        return self._context.execution_id

    async def start_child(
        self,
        name: str,
        inputs: JsonValue,
        *,
        key: str,
        environment_imports: dict[str, str] | None = None,
    ) -> ChildProgramExecution:
        declared_imports = self._placement.child_imports.get(name, {})
        if environment_imports is not None and environment_imports != declared_imports:
            raise ValueError("Child environment imports must match its published bindings")
        request = child_request(RunRequest.model_validate(self._children[name]), self._context)
        if not isinstance(request.input, dict):
            raise ValueError("Prepared child input must be an object")
        payload = dict(request.input)
        payload["inputs"] = inputs
        request = request.model_copy(update={"input": payload}, deep=True)
        async with engine_errors():
            handle = await self._operations.start_child(
                request, key=key, environment_imports=declared_imports
            )
        return ChildProgramExecution(
            handle,
            partial(self._cancel_child_waits, handle.run_id) if self._cancellation else None,
        )

    async def _cancel_child_waits(self, execution_id: str) -> None:
        if self._cancellation is not None:
            await self._operations.invoke(
                InvocationRequest(
                    function=self._cancellation,
                    kwargs={
                        "execution_id": execution_id,
                        "root_execution_id": self._context.root_execution_id,
                    },
                ),
                target=self._element_target,
            )

    async def invoke_element(
        self,
        bundle: ElementBundle,
        inputs: JsonValue,
        *,
        key: str,
        execution: ExecutionSelection | None = None,
    ) -> JsonValue:
        call = ElementCall(
            bundle=bundle,
            specifications=self._specifications.for_bundle(bundle),
            context=self._context,
            key=key,
            step=None
            if bundle.root.category == ResourceCategory.OPERATION
            else StepContext(uid=key),
            receiver=self._receiver,
        )
        async with engine_errors():
            return await self._operations.invoke(
                InvocationRequest.create(
                    invoke_element,
                    kwargs={"inputs": inputs, "call": call.model_dump(mode="json")},
                ),
                target=self._target(execution),
            )

    async def receive(self, name: str, *, timeout: float | None = None) -> JsonValue:
        async with engine_errors():
            return await self._operations.receive(name, timeout=timeout)

    async def sleep(self, seconds: float) -> None:
        async with engine_errors():
            await self._operations.sleep(seconds)
