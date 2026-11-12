"""Installed pure child programs and definitions shared across real execution hosts."""

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramCallStep,
    ProgramTarget,
)
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy


class CounterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: int = 3


async def counter(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, CounterConfig) and isinstance(inputs, dict)
    value = inputs["state"]
    assert isinstance(value, int)
    return {
        "state": value + 1,
        "done": value + 1 >= config.target,
        "iteration": inputs["iteration"],
    }


COORDINATORS = (
    CoordinatorRegistration(
        "composition_counter", "1", CounterConfig, CustomCoordinatorStrategy(counter)
    ),
)


def mapped_program(body: ProgramTarget, *, concurrency: int = 2) -> CustomCoordinatorDefinition:
    return CustomCoordinatorDefinition(
        implementation="map",
        version="1",
        children={"body": body},
        config={
            "concurrency": concurrency,
            "max_items": 20,
            "inputs": {"name": PathBinding(path=("item",)).model_dump(mode="json")},
        },
    )


def repeated_program(body: ProgramTarget, *, bound: int = 5) -> CustomCoordinatorDefinition:
    return CustomCoordinatorDefinition(
        implementation="repeat",
        version="1",
        children={"body": body},
        config={"max_iterations": bound},
    )


def composition_graph(program: ProgramTarget) -> GraphDefinition:
    return GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="compose",
                program=program,
                inputs={"items": PathBinding(path=("values", "items"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        entry="compose",
        exit="compose",
        inputs={"values": PathBinding(path=())},
        outputs={"result": PathBinding(path=("values",))},
    )
