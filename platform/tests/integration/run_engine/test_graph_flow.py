"""Real graph children and condition receivers preserve admitted branch-local values."""

import pytest
from support.graph_routes import conditional_values
from support.scenarios import publish, run
from support.typed_programs import APPLICATION_PROGRAMS

from flareward.executions.domain.models import ExecutionPhase
from flareward.programs.domain.models import ConditionalRoute, JoinPolicy


@pytest.fixture(autouse=True)
def installed(application):
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("selected", [True, False])
async def test_conditional_consumer_only_runs_with_its_producer(platform, profile, selected):
    revision = await publish(
        platform, "branch-values", conditional_values(selected=selected, profile=profile)
    )
    execution = await run(platform, revision, {})
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result == {"result": "finished"}
    children = await platform.executions.children(execution.execution_id, platform.owner)
    addresses = {child.body_path for child in children}
    assert (("consume",) in addresses) is selected
    assert (("left",) in addresses) is selected
    assert (("right",) in addresses) is not selected
    if selected:
        consumed = next(child for child in children if child.body_path == ("consume",))
        assert consumed.inputs == "left" and consumed.result == "left"


async def test_unproven_cycle_still_checks_missing_values_at_runtime(platform):
    graph = conditional_values(selected=False, consume_after_join=True)
    cyclic = graph.model_copy(
        update={
            "edges": {
                source: targets for source, targets in graph.edges.items() if source != "consume"
            },
            "conditions": (
                *graph.conditions,
                ConditionalRoute(
                    source="consume",
                    condition=graph.resources[0].key,
                    branches={"true": "route", "false": "finish"},
                ),
            ),
        }
    )
    revision = await publish(platform, "cyclic", cyclic)
    execution = await run(platform, revision, {})
    assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract"
    assert "Binding cannot resolve a portable value" in execution.failure.message


async def test_all_predecessor_admission_does_not_certify_exit_reachability(platform):
    revision = await publish(
        platform,
        "static-all",
        conditional_values(
            selected=False,
            consume_after_join=True,
            join_policy=JoinPolicy.ALL,
        ),
    )
    execution = await run(platform, revision, {})
    assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract"
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert not any(child.body_path == ("consume",) for child in children)
