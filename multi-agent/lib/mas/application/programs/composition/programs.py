"""Composition semantics use existing child, message and timer ports on either host."""

from mas.application.execution.ports import ExecutionError
from mas.application.programs.composition.models import (
    ChooseConfig,
    ChooseResult,
    MapConfig,
    MapInput,
    MapItem,
    MapResult,
    MapScope,
    RepeatConfig,
    RepeatInput,
    RepeatReason,
    RepeatResult,
    RepeatScope,
    WaitConfig,
    WaitReason,
    WaitResult,
)
from mas.application.programs.composition.scope import ChildCalls
from mas.application.programs.ports import ProgramRuntime
from mas.application.programs.registry import ApplicationRegistration
from mas.domain.execution.models import ExecutionFailure, FailureKind
from mas.domain.programs.bindings import BindingError, project
from pydantic import BaseModel, JsonValue, ValidationError


class CompositionContractError(ExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(
            ExecutionFailure(
                kind=FailureKind.CONTRACT, code="composition_contract", message=message
            )
        )


class MapCoordinator:
    def __init__(self, runtime: ProgramRuntime, config: MapConfig) -> None:
        self._runtime, self._config = runtime, config

    async def run(self, request: MapInput) -> MapResult:
        if len(request.items) > self._config.max_items:
            raise CompositionContractError("Map input exceeds its published item bound")
        remaining = iter(enumerate(request.items))
        results: list[MapItem | None] = [None] * len(request.items)
        async with ChildCalls(self._runtime) as calls:

            async def work() -> None:
                for index, item in remaining:
                    scope = MapScope(item=item, index=index, context=request.context).model_dump(
                        mode="json"
                    )
                    inputs = (
                        project(self._config.inputs, scope)
                        if self._config.inputs is not None
                        else scope
                    )
                    execution_id, result = await calls.call(
                        self._config.body, inputs, key=f"item-{index}"
                    )
                    results[index] = MapItem(index=index, execution_id=execution_id, value=result)

            await calls.gather(
                work() for _ in range(min(self._config.concurrency, len(request.items)))
            )
        assert all(value is not None for value in results)
        return MapResult(items=tuple(value for value in results if value is not None))


class RepeatCoordinator:
    def __init__(self, runtime: ProgramRuntime, config: RepeatConfig) -> None:
        self._runtime, self._config = runtime, config

    async def run(self, request: RepeatInput) -> RepeatResult:
        state = request.state
        async with ChildCalls(self._runtime) as calls:
            for iteration in range(self._config.max_iterations):
                scope = RepeatScope(
                    state=state, iteration=iteration, context=request.context
                ).model_dump(mode="json")
                inputs = (
                    project(self._config.inputs, scope)
                    if self._config.inputs is not None
                    else scope
                )
                execution_id, result = await calls.call(
                    self._config.body, inputs, key=f"iteration-{iteration}"
                )
                projected = project(
                    {"state": self._config.state, "done": self._config.until}, result
                )
                if not isinstance(projected["done"], bool):
                    raise CompositionContractError(
                        "Repeat completion predicate must return a boolean"
                    )
                state = projected["state"]
                if projected["done"] or iteration + 1 == self._config.max_iterations:
                    return RepeatResult(
                        reason=RepeatReason.SATISFIED
                        if projected["done"]
                        else RepeatReason.LIMIT_REACHED,
                        iterations=iteration + 1,
                        state=state,
                        last=result,
                        execution_id=execution_id,
                    )
        raise AssertionError("Repeat requires a positive bound")


async def map_program(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, MapConfig)
    try:
        return (
            await MapCoordinator(runtime, config).run(MapInput.model_validate(inputs))
        ).model_dump(mode="json")
    except ValidationError, BindingError:
        raise CompositionContractError("Map input or data binding violates its contract") from None


async def repeat_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, RepeatConfig)
    try:
        return (
            await RepeatCoordinator(runtime, config).run(RepeatInput.model_validate(inputs))
        ).model_dump(mode="json")
    except ValidationError, BindingError:
        raise CompositionContractError(
            "Repeat input or data binding violates its contract"
        ) from None


async def choose_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, ChooseConfig)
    try:
        selected = project({"choice": config.selector}, inputs)["choice"]
        if not isinstance(selected, str) or selected not in config.branches:
            raise CompositionContractError("Choose returned an undeclared branch")
        projected = project(config.inputs, inputs) if config.inputs is not None else inputs
        async with ChildCalls(runtime) as calls:
            execution_id, result = await calls.call(
                config.branches[selected], projected, key="selected"
            )
        return ChooseResult(branch=selected, execution_id=execution_id, value=result).model_dump(
            mode="json"
        )
    except BindingError:
        raise CompositionContractError("Choose data binding violates its contract") from None


async def wait_program(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, WaitConfig)
    try:
        value = await runtime.receive(config.channel, timeout=config.timeout_seconds)
    except TimeoutError:
        return WaitResult(reason=WaitReason.TIMED_OUT).model_dump(mode="json")
    return WaitResult(reason=WaitReason.RECEIVED, value=value).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "map",
        "1",
        MapConfig,
        map_program,
        "Map",
        "Call a pinned child for each item with bounded concurrency and fail-fast joining",
        MapInput,
        MapResult,
    ),
    ApplicationRegistration(
        "repeat",
        "1",
        RepeatConfig,
        repeat_program,
        "Repeat",
        "Repeat a pinned child until a recorded boolean result or an explicit iteration bound",
        RepeatInput,
        RepeatResult,
    ),
    ApplicationRegistration(
        "choose",
        "1",
        ChooseConfig,
        choose_program,
        "Choose",
        "Select exactly one declared child from a recorded branch label",
        result_model=ChooseResult,
    ),
    ApplicationRegistration(
        "wait",
        "1",
        WaitConfig,
        wait_program,
        "Wait",
        "Await an execution-scoped event or deadline; human business approval uses Human Review",
        result_model=WaitResult,
    ),
)
