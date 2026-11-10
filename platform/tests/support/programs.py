"""Installed application programs import only application-owned contracts."""

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ChildContract, ProgramRuntime
from lumora.programs.registry import ApplicationRegistration
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


APPLICATION_PROGRAMS = (
    ApplicationRegistration("greeting", "1", GreetingConfig, greeting_program),
    ApplicationRegistration("composed", "1", ComposedConfig, composed_program),
    ApplicationRegistration("waiting", "1", EmptyProgramConfig, waiting_program),
    ApplicationRegistration("parallel_waiting", "1", EmptyProgramConfig, parallel_waiting_program),
    ApplicationRegistration("invoking", "1", InvokeConfig, invoking_program),
    ApplicationRegistration("typed_operation", "1", InvokeConfig, operation_program),
    ApplicationRegistration("operation", "1", InvokeConfig, forward_operation_program),
    ApplicationRegistration("placed_operation", "1", PlacedInvokeConfig, placed_operation_program),
    ApplicationRegistration("parallel_operation", "1", InvokeConfig, parallel_operation_program),
    ApplicationRegistration(
        "borrowing_operation", "1", PlacedInvokeConfig, borrowing_operation_program
    ),
    ApplicationRegistration("recovery", "1", RecoveryConfig, recovery_program),
)
