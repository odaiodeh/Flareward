"""Graph authoring analysis preserves domain checks without runtime construction."""

import asyncio
import threading
from unittest.mock import create_autospec

import pytest
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import BlueprintDocument, BlueprintResolutionSource
from mas.core.element_meta import ElementConfigMeta
from mas.core.identity import Identity
from mas.core.resource_models import StepDef
from mas.graph.analysis import BlueprintGraphAnalysisService, GraphAnalysisError
from mas.graph.graph_plan import GraphPlan
from mas.graph.models import Step
from mas.graph.plan_builder import PlanBuilder
from mas.graph.topology.path_algorithms import GraphAnalysisLimit, PathEnumerator
from mas.graph.validation.fix_models import FixType
from mas.graph.validation.interfaces import ValidationProvider
from mas.graph.validation.models import MessageCode, ValidationReport
from mas.graph.validation.service import GraphValidationService
from mas.graph.validation.settings import ValidationSettings
from support.elements import EchoConfig, EchoSpec
from support.resolution import resolve_configurations


@pytest.fixture
def graph_case(application):
    class Consumer(EchoSpec):
        type_key = "consume_output"
        reads, writes = {"output"}, set()

    application.elements.register_spec_class(Consumer)
    metadata = tuple(
        ElementConfigMeta(
            rid=rid,
            category="nodes",
            type_key=kind,
            name=rid,
            config=EchoConfig(dependency="unused"),
        )
        for rid, kind in (("producer", "platform_echo"), ("consumer", "consume_output"))
    )
    source = create_autospec(BlueprintResolutionSource, instance=True)
    source.resolve.return_value = resolve_configurations(
        metadata,
        plan=(
            StepDef(uid="produce", node="producer"),
            StepDef(uid="consume", node="consumer", after="produce"),
        ),
    )
    authoring = create_autospec(BlueprintAuthoringService, instance=True)
    authoring.get.return_value = BlueprintDocument(
        blueprint_id="saved", identity=application.owner, spec_dict={"plan": []}
    )
    validation = GraphValidationService(
        application.elements,
        ValidationSettings(
            required_start_nodes={"platform_echo"},
            required_end_nodes={"consume_output"},
        ),
    )
    service = BlueprintGraphAnalysisService(authoring, source, application.elements, validation)
    return service, source, authoring, validation


async def test_graph_analysis_follows_upstream_channel_flow_and_preserves_named_checks(
    application, graph_case
):
    service, source, authoring, _ = graph_case
    result = await service.analyze(application.owner, spec={"plan": []})
    assert result.validation_result.is_valid, result
    channel = next(
        report for report in result.validation_result.reports if report.validator_name == "channel"
    )
    assert channel.details.path_validations["path_1"].steps == ["produce", "consume"]
    assert not result.fix_suggestions
    authoring.get.assert_not_awaited()
    required = await service.analyze(
        application.owner, blueprint_id="saved", validator="required_nodes"
    )
    assert (
        required.validation_result.is_valid
        and required.validation_result.validator_name == "required_nodes"
    )
    source.resolve.assert_awaited_with({"plan": []}, application.owner, stored=True)


async def test_saved_graph_ownership_precedes_reference_resolution(application, graph_case):
    service, source, authoring, _ = graph_case
    authoring.get.side_effect = PermissionError("Denied")
    with pytest.raises(PermissionError):
        await service.analyze(Identity.user("foreign"), blueprint_id="saved")
    source.resolve.assert_not_awaited()


async def test_analysis_rejects_missing_resources_bad_topology_and_unknown_checks(
    application, graph_case
):
    service, source, _, _ = graph_case
    with pytest.raises(ValueError, match="Unknown graph validator"):
        await service.analyze(application.owner, spec={}, validator="unknown-private")
    source.resolve.assert_not_awaited()
    resolution = source.resolve.return_value
    resolution.missing["hidden"] = "private reason"
    with pytest.raises(KeyError, match="Blueprint resource not found"):
        await service.analyze(application.owner, spec={})
    resolution.missing.clear()
    resolution.blueprint.plan = (StepDef(uid="bad", node="unknown"),)
    with pytest.raises(ValueError, match="Invalid blueprint graph"):
        await service.analyze(application.owner, spec={})
    resolution.blueprint.plan = (StepDef(uid="bad", node="producer", branches={"go": "bad"}),)
    with pytest.raises(ValueError, match="Invalid blueprint graph"):
        await service.analyze(application.owner, spec={})


def test_cycle_fix_suggestions_remove_actual_edges_and_break_the_cycle(application, graph_case):
    _, source, _, validation = graph_case
    blueprint = source.resolve.return_value.blueprint
    blueprint.plan = tuple(
        StepDef(uid=uid, node="producer", after=parent)
        for uid, parent in (("a", "c"), ("b", "a"), ("c", "b"))
    )
    plan = PlanBuilder(application.elements).build(blueprint)
    report, suggestions = validation.validate_and_suggest(plan, "cycle")
    assert not report.is_valid and report.messages[0].code == MessageCode.CYCLE_DETECTED
    removals = [fix for fix in suggestions if fix.context.get("fix_type") == "remove_dependency"]
    assert len(removals) == 3
    for fix in removals:
        repaired = PlanBuilder(application.elements).build(blueprint)
        dependent = repaired.get_step(fix.context["dependent_step"])
        dependent.after.remove(fix.context["dependency_step"])
        assert validation.run_validator("cycle", repaired).is_valid


def test_required_node_limits_suggest_removals_and_missing_types_suggest_additions(
    application, graph_case
):
    _, source, _, validation = graph_case
    blueprint = source.resolve.return_value.blueprint
    blueprint.plan = (StepDef(uid="a", node="producer"), StepDef(uid="b", node="producer"))
    report, fixes = validation.validate_required_nodes(
        PlanBuilder(application.elements).build(blueprint)
    )
    assert not report.is_valid
    removals = [fix for fix in fixes if fix.fix_type == FixType.REMOVE_NODE]
    assert {fix.code for fix in removals} == {
        MessageCode.TOO_MANY_START_NODES,
        MessageCode.TOO_MANY_END_NODES,
    }
    additions = [fix for fix in fixes if fix.fix_type == FixType.ADD_NODE]
    assert {fix.context["suggested_node_type"] for fix in additions} == {"consume_output"}
    assert all(fix.context["node_category"] == "nodes" for fix in additions)


def test_provider_registration_is_explicit_and_scoped_to_each_service(application):
    class Custom(ValidationProvider):
        name = "custom"

        def validate(self, plan):
            return ValidationReport(validator_name=self.name, is_valid=True)

    default = GraphValidationService(application.elements)
    explicit = GraphValidationService(application.elements, validators=[Custom()], fix_providers=[])
    assert "custom" not in default.get_validation_names()
    assert explicit.get_validation_names() == ["custom"]
    with pytest.raises(ValueError, match="distinct"):
        GraphValidationService(application.elements, validators=[Custom(), Custom()])


@pytest.mark.parametrize("cancel", [False, True])
async def test_analysis_owns_cpu_work_and_sanitizes_installed_provider_failures(
    application, graph_case, cancel
):
    _, source, authoring, _ = graph_case
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    loop_thread = threading.get_ident()

    class Blocking(ValidationProvider):
        name = "blocking"

        def validate(self, plan):
            assert threading.get_ident() != loop_thread
            entered.set()
            assert release.wait(5)
            finished.set()
            raise RuntimeError("private-provider-failure")

    validation = GraphValidationService(
        application.elements, validators=[Blocking()], fix_providers=[]
    )
    service = BlueprintGraphAnalysisService(authoring, source, application.elements, validation)
    task = asyncio.create_task(service.analyze(application.owner, spec={}))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if cancel:
            task.cancel()
            task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError if cancel else GraphAnalysisError) as raised:
        await task
    assert "private-provider-failure" not in str(raised.value) and finished.is_set()


def test_path_analysis_is_deterministic_and_bounded():
    plan = GraphPlan()
    for uid, after in (("root", []), ("b", ["root"]), ("a", ["root"])):
        plan.add_step(Step(uid=uid, category="nodes", rid=uid, type_key="test", after=after))
    assert PathEnumerator(plan).enumerate_paths() == {
        "path_1": ["root", "a"],
        "path_2": ["root", "b"],
    }
    with pytest.raises(GraphAnalysisLimit):
        PathEnumerator(plan, max_paths=1).enumerate_paths()
    with pytest.raises(GraphAnalysisLimit):
        PathEnumerator(plan, max_depth=1).enumerate_paths()
