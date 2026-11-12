"""Ordinary graph/Repeat composition around a published Engineering contract."""

from lumora.programs.composition.models import RepeatConfig
from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    GraphWritePolicy,
    ProgramBody,
    ProgramCallStep,
    ProgramRef,
    ResultRoute,
)
from plugins.adlc.programs.program import EngineeringInput, EngineeringOutcome


def delivery_graph(engineering: ProgramRef, *, iterations: int) -> GraphDefinition:
    identity = ProgramBody(
        implementation=CustomCoordinatorDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={},
    )
    attempt = ProgramBody(
        input_schema=EngineeringInput.model_json_schema(),
        implementation=GraphDefinition(
            write_policy=GraphWritePolicy.REDUCE,
            steps=(
                ProgramCallStep(
                    uid="work", program=engineering, inputs=PathBinding(path=("input",))
                ),
                ProgramCallStep(
                    uid="accepted",
                    program=identity,
                    inputs=LiteralBinding(value=True),
                    outputs={"values": LiteralBinding(value={"done": True})},
                ),
                ProgramCallStep(
                    uid="rejected",
                    program=identity,
                    inputs=LiteralBinding(value=False),
                    outputs={"values": LiteralBinding(value={"done": False})},
                ),
                ProgramCallStep(
                    uid="finish", program=identity, inputs=PathBinding(path=("values", "done"))
                ),
            ),
            conditions=(
                ResultRoute(
                    source="work",
                    selection=PathBinding(path=("results", "work", "outcome")),
                    branches={
                        outcome: "accepted" if outcome == "verified" else "rejected"
                        for outcome in EngineeringOutcome
                    },
                ),
            ),
            edges={"accepted": ("finish",), "rejected": ("finish",)},
            entry="work",
            exit="finish",
            outputs={
                "done": PathBinding(path=("results", "finish")),
                "state": PathBinding(path=("input",)),
                "result": PathBinding(path=("results", "work")),
            },
        ),
    )
    control = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation="repeat",
            version="1",
            config=RepeatConfig(
                max_iterations=iterations,
                inputs=PathBinding(path=("state",)),
                state=PathBinding(path=("state",)),
                until=PathBinding(path=("done",)),
            ).model_dump(mode="json"),
            children={"body": attempt},
        )
    )
    return GraphDefinition(
        steps=(
            ProgramCallStep(uid="improve", program=control, inputs=PathBinding(path=("input",))),
        ),
        entry="improve",
        exit="improve",
        outputs=PathBinding(path=("results", "improve")),
    )
