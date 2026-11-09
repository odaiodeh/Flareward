"""Whole JSON values cross actual graph, Program and operation invocation boundaries."""

import pytest
from runengine.coordination.models import RunRequest
from runengine.programs.graph.inputs import GraphProgramInput
from support.scenarios import publish, run
from support.typed_programs import APPLICATION_PROGRAMS
from support.value_operations import ELEMENT_SPECIFICATIONS, ArraySpec, LengthSpec, value_graph

from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.adapters.run_engine.shared.models import ProgramPayload
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.models import ExecutionPhase
from flareward.programs.composition.programs import APPLICATION_PROGRAMS as CONTROLS
from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    JoinPolicy,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramCallStep,
)


@pytest.fixture(autouse=True)
def installed(application):
    for registration in (*CONTROLS, *APPLICATION_PROGRAMS):
        application.applications.register(registration)
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "specification,inputs,expected", [(ArraySpec, [2, 3], [4, 6]), (LengthSpec, "word", 8)]
)
async def test_graph_operations_consume_and_return_root_values(
    platform, profile, specification, inputs, expected
):
    revision = await publish(
        platform,
        "operation",
        value_graph(specification, profile),
        input_schema={},
        output_schema={},
    )
    execution = await run(platform, revision, inputs)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == expected and execution.inputs == inputs


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "specification,inputs,expected", [(ArraySpec, [2, 3], [4, 6]), (LengthSpec, "word", 8)]
)
async def test_backend_program_invokes_root_value_operations_without_graph_context(
    application, platform, profile, specification, inputs, expected
):
    graph = value_graph(specification)
    bundle = ElementBundleResolver(application.elements).resolve(
        graph.steps[0].element, graph.resources
    )
    revision = await publish(
        platform,
        "backend",
        ApplicationDefinition(
            implementation="operation",
            version="1",
            config={"bundle": bundle.model_dump(mode="json")},
        ),
        execution_profile=profile,
        input_schema={},
        output_schema={},
    )
    execution = await run(platform, revision, inputs)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == expected


@pytest.mark.parametrize("owned", [True, False])
@pytest.mark.parametrize("inputs", [[1, 2], "text", 3, True, None])
async def test_graph_calls_pass_whole_values_to_owned_and_pinned_programs(platform, owned, inputs):
    child = ProgramBody(
        implementation=ApplicationDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={},
    )
    target = (
        child
        if owned
        else (
            await publish(
                platform, "identity", child.implementation, input_schema={}, output_schema={}
            )
        ).reference
    )
    revision = await publish(
        platform,
        "graph",
        GraphDefinition(
            steps=(
                ProgramCallStep(uid="child", program=target, inputs=PathBinding(path=("input",))),
            ),
            entry="child",
            exit="child",
            outputs=PathBinding(path=("results", "child")),
        ),
        input_schema={},
        output_schema={},
    )
    execution = await run(platform, revision, inputs)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == inputs
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == 1 and children[0].inputs == inputs and children[0].result == inputs


@pytest.mark.parametrize("kind", ["map", "repeat", "choose"])
async def test_controls_use_whole_value_child_projections(platform, kind):
    child = ProgramBody(
        implementation=ApplicationDefinition(implementation="numbers_program", version="1"),
        input_schema={"type": "array"},
        output_schema={"type": "array"},
    )
    source = {"map": "item", "repeat": "state", "choose": "numbers"}[kind]
    config = {"inputs": PathBinding(path=(source,)).model_dump(mode="json")}
    if kind == "repeat":
        config.update(
            {
                "state": PathBinding(path=()).model_dump(mode="json"),
                "until": LiteralBinding(value=True).model_dump(mode="json"),
            }
        )
    elif kind == "choose":
        config["branches"] = {"approved": "body"}
    revision = await publish(
        platform,
        kind,
        ApplicationDefinition(
            implementation=kind,
            version="1",
            children={"body": child},
            config=config,
        ),
    )
    inputs = {
        "map": {"items": [[1], [2, 3]]},
        "repeat": {"state": [1, 2]},
        "choose": {"choice": "approved", "numbers": [1, 2]},
    }[kind]
    execution = await run(platform, revision, inputs)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    if kind == "map":
        assert [item["value"] for item in execution.result["items"]] == [[2], [4, 6]]
    elif kind == "repeat":
        assert execution.result["reason"] == "satisfied" and execution.result["state"] == [2, 4]
    else:
        assert execution.result["value"] == [2, 4]


async def test_graph_output_literal_can_be_a_scalar_or_null(platform):
    graph = value_graph(ArraySpec).model_copy(update={"outputs": LiteralBinding(value=None)})
    revision = await publish(
        platform, "null", graph, input_schema={}, output_schema={"type": "null"}
    )
    execution = await run(platform, revision, [1])
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result is None


async def test_missing_dynamic_projection_is_a_safe_contract_failure(platform):
    graph = value_graph(ArraySpec)
    step = graph.steps[0].model_copy(update={"inputs": PathBinding(path=("input", "missing"))})
    revision = await publish(
        platform,
        "missing",
        graph.model_copy(update={"steps": (step,)}),
        output_schema={"type": "array"},
    )
    execution = await run(platform, revision, {"private": "input-value"})
    assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract"
    assert "input-value" not in execution.failure.message


@pytest.mark.parametrize("caller_kind", ["graph", "application"])
async def test_array_graph_revision_composes_with_graph_and_backend_coordinators(
    platform, caller_kind
):
    child = await publish(
        platform,
        "array",
        value_graph(ArraySpec, "process"),
        input_schema={"type": "array"},
        output_schema={"type": "array"},
    )
    implementation = (
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="call", program=child.reference, inputs=PathBinding(path=("input",))
                ),
            ),
            entry="call",
            exit="call",
            outputs=PathBinding(path=("results", "call")),
        )
        if caller_kind == "graph"
        else ApplicationDefinition(
            implementation="composed", version="1", children={"greet": child.reference}
        )
    )
    revision = await publish(
        platform,
        "caller",
        implementation,
        input_schema={"type": "array"},
        output_schema={"type": "array"},
    )
    execution = await run(platform, revision, [1, 3])
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == [2, 6]
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == 1 and children[0].program == child.reference


@pytest.mark.parametrize("join_policy", list(JoinPolicy))
async def test_parallel_program_results_have_independent_keys_and_join_as_values(
    platform, join_policy
):
    identity = ProgramBody(
        implementation=ApplicationDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={},
    )
    numbers = ProgramBody(
        implementation=ApplicationDefinition(implementation="numbers_program", version="1"),
        input_schema={"type": "array"},
        output_schema={"type": "array"},
    )
    graph = GraphDefinition(
        join_policy=join_policy,
        steps=(
            ProgramCallStep(uid="entry", program=identity, inputs=LiteralBinding(value=None)),
            ProgramCallStep(
                uid="left", program=numbers, inputs=PathBinding(path=("input", "left"))
            ),
            ProgramCallStep(
                uid="right", program=numbers, inputs=PathBinding(path=("input", "right"))
            ),
            ProgramCallStep(
                uid="join",
                program=identity,
                inputs={
                    "left": PathBinding(path=("results", "left")),
                    "right": PathBinding(path=("results", "right")),
                },
            ),
        ),
        edges={"entry": ("left", "right"), "left": ("join",), "right": ("join",)},
        entry="entry",
        exit="join",
        outputs=PathBinding(path=("results", "join")),
    )
    revision = await publish(platform, "parallel", graph)
    compiled = await platform.compiler.compile(
        revision, platform.owner, ExecutionContext(identity=platform.owner)
    )
    payload = ProgramPayload.model_validate(compiled.input)
    native = GraphProgramInput.model_validate(
        RunRequest.model_validate(payload.graph_request).input
    )
    assert native.join_policy.value == join_policy.value
    execution = await run(platform, revision, {"left": [1], "right": [2, 3]})
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == {"left": [2], "right": [4, 6]}
