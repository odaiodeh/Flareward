"""Actual native routing uses portable results, with no MAS state or condition resource."""

import pytest
from runengine.coordination.models import RunRequest
from runengine.programs.graph.inputs import GraphProgramInput
from support.operations import operation_resources
from support.result_routing import result_graph
from support.scenarios import publish, run
from support.typed_programs import COORDINATORS

from lumora.executions.adapters.run_engine.shared.models import ProgramPayload
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionPhase, FailureKind
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import ConditionalRoute, OperationStep
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory


@pytest.fixture(autouse=True)
def installed(application):
    for registration in COORDINATORS:
        application.applications.register(registration)


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "value,visited",
    [
        (True, {"yes"}),
        (False, {"no"}),
        ("approved", {"yes"}),
        ("changes_required", {"no"}),
        (["approved", "changes_required"], {"yes", "no"}),
    ],
)
async def test_result_routes_choose_declared_successors_and_join_once(
    platform, profile, value, visited
):
    revision = await publish(
        platform, "result-route", result_graph(profile), input_schema={}, output_schema={}
    )
    request = await platform.compiler.compile(
        revision, platform.owner, ExecutionContext(identity=platform.owner)
    )
    payload = ProgramPayload.model_validate(request.input)
    native = GraphProgramInput.model_validate(
        RunRequest.model_validate(payload.implementation.request).input
    )
    assert native.targets["condition_decide"]["runner_type"] == profile
    execution = await run(platform, revision, value)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert set(execution.result) == {"decide", "finish", *visited}
    assert execution.result["finish"] == "finished"
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == len(visited) + 2


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "value", ["private-unknown-label", ["approved", "private-unknown-label"], 1, None]
)
async def test_invalid_complete_selection_fails_without_disclosing_values(platform, profile, value):
    revision = await publish(
        platform, "invalid-selection", result_graph(profile), input_schema={}, output_schema={}
    )
    execution = await run(platform, revision, value)
    assert execution.phase == ExecutionPhase.FAILED
    assert execution.failure.kind == FailureKind.CONTRACT
    assert "private-unknown-label" not in execution.failure.message
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == 1


async def test_result_projection_selects_nested_output(platform):
    revision = await publish(
        platform,
        "nested-result",
        result_graph(selection=PathBinding(path=("results", "decide", "outcome"))),
        input_schema={},
        output_schema={},
    )
    execution = await run(
        platform, revision, {"outcome": "approved", "data": {"artifact": "revision"}}
    )
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert "yes" in execution.result and "no" not in execution.result


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_route_uses_typed_operation_output_without_graph_context(platform, profile):
    graph = result_graph(profile, selection=PathBinding(path=("results", "decide", "text")))
    resources = operation_resources()
    graph = graph.model_copy(
        update={
            "resources": resources,
            "steps": (
                OperationStep(
                    uid="decide",
                    element=resources[0].key,
                    inputs={"text": PathBinding(path=("input",))},
                    execution=ExecutionSelection(profile=profile),
                ),
                *graph.steps[1:],
            ),
            "conditions": (
                graph.conditions[0].model_copy(
                    update={
                        "branches": {"typed:middle:approved": "yes", "typed:middle:rejected": "no"},
                    }
                ),
            ),
        }
    )
    revision = await publish(
        platform, "operation-result-route", graph, input_schema={}, output_schema={}
    )
    result = await run(platform, revision, "approved")
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert "yes" in result.result and "no" not in result.result


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_result_route_coexists_with_explicit_condition_adapter(platform, profile):
    graph = result_graph(profile)
    condition = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.CONDITION, rid="fixed"),
        type_key="router_boolean",
        config={"boolean_value": True},
    )
    graph = graph.model_copy(
        update={
            "resources": (condition,),
            "conditions": (
                *graph.conditions,
                ConditionalRoute(
                    source="yes",
                    condition=condition.key,
                    branches={"true": "finish", "false": "finish"},
                    execution=ExecutionSelection(profile=profile),
                ),
            ),
            "edges": {"no": ("finish",)},
        }
    )
    revision = await publish(platform, "mixed-routing", graph, input_schema={}, output_schema={})
    execution = await run(platform, revision, "approved")
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert set(execution.result) == {"decide", "yes", "finish"}
