"""Actual node results enforce the application state boundary on both receiver types."""

import pytest
from support.scenarios import publish, run
from support.state_nodes import ELEMENT_SPECIFICATIONS, Mutation, state_graph
from support.typed_programs import COORDINATORS

from lumora.executions.domain.models import ExecutionPhase
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
)


@pytest.fixture(autouse=True)
def installed(application):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    for registration in COORDINATORS:
        application.applications.register(registration)


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("mutation", list(Mutation))
async def test_node_returns_enforce_shape_and_declared_write_permissions(
    platform, profile, mutation
):
    revision = await publish(platform, "state", state_graph(mutation, profile))
    execution = await run(platform, revision, {})
    if mutation == Mutation.VALID:
        assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
        assert execution.result == {"answer": "answer"}
    else:
        assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract"
        assert "private" not in execution.failure.message


@pytest.mark.parametrize("boundary", ["initial", "output"])
async def test_dynamic_channel_contract_errors_hide_values_and_preserve_effect_order(
    platform, boundary
):
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={},
    )
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="identity",
                program=body,
                inputs=PathBinding(path=("input", "prompt")),
                outputs={"values": PathBinding(path=())} if boundary == "output" else {},
            ),
        ),
        entry="identity",
        exit="identity",
        inputs={"values": PathBinding(path=("prompt",))} if boundary == "initial" else {},
    )
    revision = await publish(platform, boundary, graph)
    execution = await run(platform, revision, {"prompt": "private-invalid-channel-value"})
    assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract"
    assert (
        "private" not in execution.failure.message
        and "invalid-channel-value" not in execution.failure.message
    )
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == (0 if boundary == "initial" else 1)
