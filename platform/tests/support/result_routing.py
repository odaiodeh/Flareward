"""Portable result-routing scenarios shared by publication and native tests."""

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ResultRoute,
)


def result_graph(profile="thread", *, schema=None, selection=None):
    identity = ProgramBody(
        implementation=CustomCoordinatorDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={} if schema is None else schema,
    )
    branch = identity.model_copy(update={"output_schema": {"type": "string"}})
    return GraphDefinition(
        steps=(
            ProgramCallStep(uid="decide", program=identity, inputs=PathBinding(path=("input",))),
            ProgramCallStep(uid="yes", program=branch, inputs=LiteralBinding(value="accepted")),
            ProgramCallStep(uid="no", program=branch, inputs=LiteralBinding(value="revise")),
            ProgramCallStep(uid="finish", program=branch, inputs=LiteralBinding(value="finished")),
        ),
        conditions=(
            ResultRoute(
                source="decide",
                selection=selection or PathBinding(path=("results", "decide")),
                branches={
                    "approved": "yes",
                    "changes_required": "no",
                    "true": "yes",
                    "false": "no",
                },
                execution=ExecutionSelection(profile=profile),
            ),
        ),
        edges={"yes": ("finish",), "no": ("finish",)},
        entry="decide",
        exit="finish",
        outputs=PathBinding(path=("results",)),
    )
