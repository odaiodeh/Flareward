"""Installed application programs import only application-owned contracts."""

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ChildContract, ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle
from support.recovery import RecoveryConfig, recovery_program

__runengine_contract__ = "lumora-test-programs-v1"


class GreetingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefix: str = "hello "


async def greeting_program(runtime: ProgramRuntime, inputs: dict, config: GreetingConfig) -> dict:
    return {"answer": config.prefix + inputs["name"]}


class EmptyProgramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComposedConfig(EmptyProgramConfig):
    def child_contracts(self) -> dict[str, ChildContract]:
        return {"greet": ChildContract()}


async def composed_program(runtime: ProgramRuntime, inputs: dict, config: ComposedConfig) -> dict:
    child = await runtime.start_child("greet", inputs, key="greet")
    return await child.result()


async def waiting_program(
    runtime: ProgramRuntime, inputs: dict, config: EmptyProgramConfig
) -> dict:
    return {"answer": await runtime.receive("answer")}


async def parallel_waiting_program(
    runtime: ProgramRuntime, inputs: dict, config: EmptyProgramConfig
) -> dict:
    left = await runtime.start_child("left", {}, key="left")
    await runtime.start_child("right", {}, key="right")
    if inputs.get("cancel_inside"):
        await runtime.receive("cancel_left")
        await left.cancel()
    return {"answer": await runtime.receive("answer")}


class InvokeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: ElementBundle


async def invoking_program(runtime: ProgramRuntime, inputs: dict, config: InvokeConfig) -> dict:
    result = await runtime.invoke_element(
        config.bundle, {"user_prompt": inputs["name"]}, key="work"
    )
    return {"answer": result["output"]}


async def operation_program(runtime: ProgramRuntime, inputs: dict, config: InvokeConfig) -> dict:
    result = await runtime.invoke_element(config.bundle, {"text": inputs["name"]}, key="typed-work")
    return {"answer": result["text"]}


async def forward_operation_program(runtime: ProgramRuntime, inputs: dict, config: InvokeConfig):
    return await runtime.invoke_element(config.bundle, inputs, key="work")


class PlacedInvokeConfig(InvokeConfig):
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)


async def placed_operation_program(
    runtime: ProgramRuntime, inputs: dict, config: PlacedInvokeConfig
):
    return await runtime.invoke_element(
        config.bundle, inputs, key="work", execution=config.execution
    )


async def parallel_operation_program(runtime: ProgramRuntime, inputs: dict, config: InvokeConfig):
    results = await asyncio.gather(
        runtime.invoke_element(config.bundle, inputs, key="left"),
        runtime.invoke_element(config.bundle, inputs, key="right"),
    )
    return dict(zip(("left", "right"), results, strict=True))


async def borrowing_operation_program(
    runtime: ProgramRuntime, inputs: dict, config: PlacedInvokeConfig
):
    before = await runtime.invoke_element(
        config.bundle, inputs, key="before", execution=config.execution
    )
    child = await runtime.start_child("greet", inputs, key="child")
    result = await child.result()
    after = await runtime.invoke_element(
        config.bundle, inputs, key="after", execution=config.execution
    )
    return {"before": before, "child": result, "after": after}


COORDINATORS = (
    CoordinatorRegistration(
        "greeting", "1", GreetingConfig, CustomCoordinatorStrategy(greeting_program)
    ),
    CoordinatorRegistration(
        "composed", "1", ComposedConfig, CustomCoordinatorStrategy(composed_program)
    ),
    CoordinatorRegistration(
        "waiting", "1", EmptyProgramConfig, CustomCoordinatorStrategy(waiting_program)
    ),
    CoordinatorRegistration(
        "parallel_waiting",
        "1",
        EmptyProgramConfig,
        CustomCoordinatorStrategy(parallel_waiting_program),
    ),
    CoordinatorRegistration(
        "invoking", "1", InvokeConfig, CustomCoordinatorStrategy(invoking_program)
    ),
    CoordinatorRegistration(
        "typed_operation", "1", InvokeConfig, CustomCoordinatorStrategy(operation_program)
    ),
    CoordinatorRegistration(
        "operation", "1", InvokeConfig, CustomCoordinatorStrategy(forward_operation_program)
    ),
    CoordinatorRegistration(
        "placed_operation",
        "1",
        PlacedInvokeConfig,
        CustomCoordinatorStrategy(placed_operation_program),
    ),
    CoordinatorRegistration(
        "parallel_operation",
        "1",
        InvokeConfig,
        CustomCoordinatorStrategy(parallel_operation_program),
    ),
    CoordinatorRegistration(
        "borrowing_operation",
        "1",
        PlacedInvokeConfig,
        CustomCoordinatorStrategy(borrowing_operation_program),
    ),
    CoordinatorRegistration(
        "recovery", "1", RecoveryConfig, CustomCoordinatorStrategy(recovery_program)
    ),
)
