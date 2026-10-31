"""Conditional work follows the same approved placement policy as node work."""

import pytest
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContext
from mas.domain.element_bundles import ResourceKey
from mas.execution.models import ExecutionPhase, FailureKind
from mas.programs.models import (
    ConditionalRoute,
    ExecutionSelection,
    GraphDefinition,
    ProgramDefinition,
)
from run_engine.models import ProgramPayload
from runengine import UnknownLabelPolicy
from runengine.coordination.models import RunRequest
from runengine.programs.graph.inputs import GraphProgramInput
from support.condition_scenarios import routing_graph
from support.scenarios import echo_graph, publish, resource, run


def conditional_graph(selection: ExecutionSelection | None = None) -> GraphDefinition:
    graph = echo_graph()
    first = graph.steps[0].model_copy(update={"execution": ExecutionSelection()})
    return graph.model_copy(
        update={
            "steps": (first, first.model_copy(update={"uid": "finish"})),
            "exit": "finish",
            "conditions": (
                ConditionalRoute(
                    source="echo",
                    condition=ResourceKey(category=ResourceCategory.CONDITION, rid="route"),
                    branches={"true": "finish", "false": "finish"},
                    execution=selection or ExecutionSelection(),
                ),
            ),
            "resources": (
                *graph.resources,
                resource(
                    "route",
                    category=ResourceCategory.CONDITION,
                    type_key="router_boolean",
                    config={"type": "router_boolean", "boolean_value": True},
                ),
            ),
        }
    )


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_condition_inherits_program_placement_and_runs_in_selected_backend(platform, profile):
    definition = ProgramDefinition(
        program_id="routing",
        name="Routing",
        owner=platform.owner,
        implementation=conditional_graph(),
        execution_profile=profile,
    )
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("routing", platform.owner)
    compiled = await platform.compiler.compile(
        revision,
        platform.owner,
        ExecutionContext(identity=platform.owner),
    )
    payload = ProgramPayload.model_validate(compiled.input)
    graph_request = RunRequest.model_validate(payload.graph_request)
    graph = GraphProgramInput.model_validate(graph_request.input)
    assert graph.unknown_label_policy == UnknownLabelPolicy.ERROR
    assert graph.targets["condition_echo"]["runner_type"] == profile
    assert (await run(platform, revision, {"name": "condition"})).result == {
        "answer": "greeting:condition",
    }


async def test_condition_cannot_select_an_undeclared_environment(platform):
    definition = ProgramDefinition(
        program_id="invalid-route",
        name="Invalid",
        owner=platform.owner,
        implementation=conditional_graph(ExecutionSelection(environment="missing")),
    )
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish(definition.program_id, platform.owner)
    with pytest.raises(ValueError, match="Undeclared environment: missing"):
        await platform.compiler.compile(
            revision, platform.owner, ExecutionContext(identity=platform.owner)
        )


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("path", [["output"], ["nodes_output", "score"]])
@pytest.mark.parametrize(("value", "chosen"), [("0.75", "yes"), ("0.25", "no")])
async def test_threshold_routes_selected_outputs_through_real_factories_and_backends(
    platform, condition_elements, profile, path, value, chosen
):
    graph = routing_graph(
        "threshold", {"input_path": path, "threshold": 0.5}, profile=profile, value=value
    )
    revision = await publish(platform, "threshold", graph)
    result = await run(platform, revision, {})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert set(result.result["steps"]) == {"score", chosen, "finish"}
    assert [message["content"] for message in result.result["visits"]] == [
        "score",
        chosen,
        "finish",
    ]


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("value", [True, False])
async def test_boolean_condition_selects_one_declared_branch(
    platform, condition_elements, profile, value
):
    revision = await publish(
        platform,
        "boolean",
        routing_graph("router_boolean", {"boolean_value": value}, profile=profile),
    )
    result = await run(platform, revision, {})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert set(result.result["steps"]) == {"score", "yes" if value else "no", "finish"}


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("recipients", [(), ("yes",), ("yes", "no")])
async def test_direct_condition_routes_real_packets_and_joins_once(
    platform, condition_elements, profile, recipients
):
    revision = await publish(
        platform,
        "direct",
        routing_graph(
            "router_direct",
            {},
            profile=profile,
            recipients=recipients,
            branches={"yes": "yes", "no": "no", "END": "finish"},
        ),
    )
    result = await run(platform, revision, {})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert set(result.result["steps"]) == {"score", "finish", *recipients}
    visits = [message["content"] for message in result.result["visits"]]
    assert visits.count("finish") == 1


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_invalid_numeric_data_cannot_silently_choose_false(
    platform, condition_elements, profile
):
    revision = await publish(
        platform,
        "invalid-data",
        routing_graph(
            "threshold",
            {"input_path": ["output"], "threshold": 1},
            profile=profile,
            value="private-invalid-number",
        ),
    )
    result = await run(platform, revision, {})
    assert result.phase == ExecutionPhase.FAILED
    assert result.failure.kind == FailureKind.APPLICATION
    assert "finite number" in result.failure.message
    assert "private-invalid-number" not in result.failure.message


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_undeclared_outcome_fails_instead_of_ending_successfully(
    platform, condition_elements, profile
):
    revision = await publish(
        platform,
        "unknown-outcome",
        routing_graph(
            "router_boolean",
            {"boolean_value": True},
            profile=profile,
            branches={"false": "no"},
        ),
    )
    result = await run(platform, revision, {})
    assert result.phase == ExecutionPhase.FAILED
    assert result.failure.kind == FailureKind.CONTRACT
    assert "undeclared branch" in result.failure.message
