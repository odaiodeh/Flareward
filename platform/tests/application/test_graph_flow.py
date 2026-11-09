"""Conditional result admission follows declared routing, without executing conditions."""

import pytest
from support.graph_routes import conditional_values
from support.typed_programs import APPLICATION_PROGRAMS

from flareward.programs.authoring import ProgramIssueCode
from flareward.programs.domain.models import JoinPolicy, ProgramDefinition
from flareward.programs.graph_flow import GraphFlow
from flareward.programs.interfaces import BindingContractError
from flareward.programs.service import ProgramContractError


@pytest.fixture(autouse=True)
def installed(application):
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)


@pytest.mark.parametrize("selected", [True, False])
async def test_optional_producer_cannot_feed_a_consumer_after_a_conditional_join(
    application, selected
):
    root = ProgramDefinition(
        program_id="conditional",
        name="Conditional",
        owner=application.owner,
        implementation=conditional_values(selected=selected, consume_after_join=True),
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "conditional", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path == ("implementation", "steps", 3, "inputs")
    with pytest.raises(ProgramContractError) as refused:
        await application.programs.publish(
            "conditional", application.owner, expected_version=saved.version
        )
    assert refused.value.issue == report.issues[0]
    corrected = root.model_copy(update={"implementation": conditional_values(selected=selected)})
    changed = await application.programs.save(
        corrected, application.owner, expected_version=saved.version
    )
    assert (
        await application.programs.validate(
            "conditional", application.owner, expected_version=changed.version
        )
    ).valid


def test_gated_consumer_and_static_all_predecessors_have_distinct_guarantees():
    GraphFlow(conditional_values()).require_result("left", "consume")
    with pytest.raises(BindingContractError, match="optional"):
        GraphFlow(conditional_values(consume_after_join=True)).require_result("left", "consume")
    GraphFlow(
        conditional_values(consume_after_join=True, join_policy=JoinPolicy.ALL)
    ).require_result("left", "consume")


def test_cycle_and_bounded_analysis_defer_unknown_guarantees_to_runtime(monkeypatch):
    graph = conditional_values(consume_after_join=True)
    cyclic = graph.model_copy(update={"edges": {**graph.edges, "finish": ("route",)}})
    GraphFlow(cyclic).require_result("left", "consume")
    monkeypatch.setattr(GraphFlow, "MAX_TERMS", 1)
    GraphFlow(graph).require_result("left", "consume")
    with pytest.raises(BindingContractError, match="own result"):
        GraphFlow(cyclic).require_result("left", "left")


async def test_mixed_routing_remains_saveable_but_cannot_publish(application):
    graph = conditional_values()
    root = ProgramDefinition(
        program_id="mixed",
        name="Mixed",
        owner=application.owner,
        implementation=graph.model_copy(update={"edges": {**graph.edges, "route": ("right",)}}),
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "mixed", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.TOPOLOGY
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            "mixed", application.owner, expected_version=saved.version
        )
