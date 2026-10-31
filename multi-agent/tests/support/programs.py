"""Installed application programs import only application-owned contracts."""

from mas.domain.element_bundles import ElementBundle
from mas.programs.ports import ProgramRuntime
from mas.programs.registry import ApplicationRegistration
from pydantic import BaseModel, ConfigDict

from support.recovery import RecoveryConfig, recovery_program

__runengine_contract__ = "unifai-test-programs-v1"


class GreetingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefix: str = "hello "


async def greeting_program(runtime: ProgramRuntime, inputs: dict, config: GreetingConfig) -> dict:
    return {"answer": config.prefix + inputs["name"]}


class EmptyProgramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def composed_program(
    runtime: ProgramRuntime, inputs: dict, config: EmptyProgramConfig
) -> dict:
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


APPLICATION_PROGRAMS = (
    ApplicationRegistration("greeting", "1", GreetingConfig, greeting_program),
    ApplicationRegistration("composed", "1", EmptyProgramConfig, composed_program),
    ApplicationRegistration("waiting", "1", EmptyProgramConfig, waiting_program),
    ApplicationRegistration("parallel_waiting", "1", EmptyProgramConfig, parallel_waiting_program),
    ApplicationRegistration("invoking", "1", InvokeConfig, invoking_program),
    ApplicationRegistration("recovery", "1", RecoveryConfig, recovery_program),
)
