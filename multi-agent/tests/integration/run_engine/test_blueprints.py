"""Existing blueprint schemas, resolver, factories, and sessions use the new engine."""

from unittest.mock import create_autospec

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintSpec
from mas.blueprints.resolver import BlueprintResolver
from mas.core.caller_scope import CallerScope
from mas.core.execution_context import ExecutionContext
from mas.core.execution_preferences import ResourceExecutionDefaults
from mas.elements.llms.mock.spec.spec import MockLLMElementSpec
from mas.elements.nodes.mock_agent.spec.spec import MockAgentNodeElementSpec
from mas.execution.service import ExecutionService
from mas.graph.state.graph_state import GraphState
from mas.programs.blueprints import BlueprintProgramImporter
from mas.programs.models import ExecutionSelection, PathBinding
from mas.programs.registry import ApplicationRegistry
from mas.programs.service import ProgramService
from mas.resources.models import Resource
from mas.resources.ports import ResourceReader
from mas.session.domain.status import SessionStatus
from mas.session.execution.program_sessions import (
    CreateProgramSession,
    ProgramSessionService,
    StartSessionTurn,
)
from outbound.memory.execution_repository import MemoryExecutionRepository
from outbound.memory.program_repository import MemoryProgramRepository
from outbound.memory.session_store import MemorySessionStore
from outbound.run_engine.compiler import ProgramCompiler
from outbound.run_engine.gateway import RunEngineGateway
from run_engine.models import ProgramPayload
from runengine.coordination.models import RunRequest
from runengine.coordination.targets import EnvironmentTarget
from runengine.invocation.config import K8sRunnerConfig, ProcessRunnerConfig, ThreadRunnerConfig
from runengine.programs.graph.inputs import GraphProgramInput
from support.scenarios import run


class NoExternalResources:
    def get_visible(self, rid, *, caller):
        raise KeyError(rid)

    def resolve_resource(self, resource, caller):
        raise AssertionError("Inline configuration must not request a live resource")


def resolved_blueprint():
    draft = BlueprintDraft(
        name="Existing blueprint",
        description="Real mock node and LLM",
        llms=[
            {
                "rid": "model",
                "name": "Mock model",
                "type": "mock",
                "config": {"type": "mock", "base_url": "http://unused.invalid"},
            }
        ],
        nodes=[
            {
                "rid": "agent",
                "name": "Existing agent",
                "type": "mock_agent_node",
                "config": {"type": "mock_agent_node", "llm": "model"},
            }
        ],
        plan=[
            {
                "uid": "respond",
                "node": "agent",
                "meta": {"description": "Imported step", "tags": ["preserved"]},
            }
        ],
    )
    return BlueprintResolver(NoExternalResources(), spec_schema=BlueprintSpec).resolve(
        draft, CallerScope()
    )


async def test_existing_blueprint_runs_with_factories_and_session_state(platform):
    elements = ElementRegistry()
    elements.register_spec_class(MockAgentNodeElementSpec)
    elements.register_spec_class(MockLLMElementSpec)
    applications = ApplicationRegistry()
    programs = ProgramService(
        MemoryProgramRepository(),
        applications,
        ElementBundleResolver(elements),
        ConfigurationSecrets(elements, None),
    )
    definition = BlueprintProgramImporter(elements).convert(
        resolved_blueprint(),
        program_id="imported",
        owner=platform.owner,
    )
    await programs.save(definition, platform.owner)
    revision = await programs.publish(definition.program_id, platform.owner)
    compiler = ProgramCompiler(
        programs, elements, applications, {"thread": ThreadRunnerConfig()}, "thread"
    )
    executions = ExecutionService(
        programs,
        MemoryExecutionRepository(),
        RunEngineGateway(platform.host, compiler),
    )
    sessions = ProgramSessionService(MemorySessionStore(), programs, executions)
    bindings = {name: PathBinding(path=(name,)) for name in GraphState.model_fields}
    record = await sessions.create(
        CreateProgramSession(
            program=revision.reference,
            blueprint_id="legacy-blueprint",
            input_bindings=bindings,
            output_bindings=bindings,
        ),
        platform.owner,
    )
    started = await sessions.start(
        record.run_id,
        StartSessionTurn(inputs={"user_prompt": "legacy input"}),
        platform.owner,
    )
    result = await executions.result(started.active_execution_id, platform.owner)
    assert result.result["nodes_output"] == {"respond": "Mock echo: legacy input"}
    finished = await sessions.refresh(record.run_id, platform.owner)
    assert finished.status == SessionStatus.COMPLETED
    assert finished.blueprint_id == "legacy-blueprint"
    assert len(finished.graph_state.messages) == 1
    assert definition.implementation.steps[0].metadata.tags == ["preserved"]
    assert definition.implementation.steps[0].metadata.description == "Imported step"
    assert len(definition.implementation.resources) == 2


def test_blueprint_import_does_not_mutate_source_metadata_and_rejects_disconnected_roots(platform):
    elements = ElementRegistry()
    elements.register_spec_class(MockAgentNodeElementSpec)
    elements.register_spec_class(MockLLMElementSpec)
    blueprint = resolved_blueprint()
    before = blueprint.model_dump_json()
    importer = BlueprintProgramImporter(elements)
    importer.convert(blueprint, program_id="copy", owner=platform.owner)
    assert blueprint.model_dump_json() == before
    disconnected = blueprint.model_copy(deep=True)
    disconnected.plan.append(disconnected.plan[0].model_copy(update={"uid": "another-root"}))
    with pytest.raises(ValueError, match="exactly one entry"):
        importer.convert(disconnected, program_id="invalid", owner=platform.owner)


@pytest.fixture
def blueprint_importer(application):
    application.elements.register_spec_class(MockAgentNodeElementSpec)
    application.elements.register_spec_class(MockLLMElementSpec)
    return BlueprintProgramImporter(application.elements)


@pytest.mark.parametrize(
    "resource_profile,step_selection,program_profile,expected",
    [
        ("process", None, "thread", "process"),
        ("process", ExecutionSelection(profile="thread"), "process", "thread"),
        (None, None, "process", "process"),
        (None, None, None, "thread"),
    ],
)
async def test_imported_resource_preference_obeys_step_program_and_platform_precedence(
    platform, blueprint_importer, resource_profile, step_selection, program_profile, expected
):
    blueprint = resolved_blueprint()
    blueprint.nodes[0].execution = ResourceExecutionDefaults(profile=resource_profile)
    definition = blueprint_importer.convert(
        blueprint, program_id="placed", owner=platform.owner, execution_profile=program_profile
    )
    graph = definition.implementation
    if step_selection is not None:
        graph = graph.model_copy(
            update={
                "steps": (graph.steps[0].model_copy(update={"execution": step_selection}),),
            }
        )
        definition = definition.model_copy(update={"implementation": graph})
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("placed", platform.owner)
    compiled = await platform.compiler.compile(
        revision, platform.owner, ExecutionContext(identity=platform.owner)
    )
    payload = ProgramPayload.model_validate(compiled.input)
    request = RunRequest.model_validate(payload.graph_request)
    prepared = GraphProgramInput.model_validate(request.input)
    if expected is None:
        assert prepared.targets["respond"] == EnvironmentTarget(name="shared").model_dump(
            mode="json"
        )
    else:
        assert prepared.targets["respond"]["runner_type"] == expected
    # Placement is execution metadata, never part of a dependency bundle's configuration.
    assert all("execution" not in resource.model_dump() for resource in graph.resources)


async def test_reused_resource_has_independent_step_placement_without_mutation(
    platform, blueprint_importer
):
    blueprint = resolved_blueprint()
    blueprint.execution_profile = "thread"
    blueprint.nodes[0].execution = ResourceExecutionDefaults(profile="thread")
    first = blueprint.plan[0]
    first.execution = ExecutionSelection(profile="process")
    blueprint.plan.append(
        first.model_copy(
            update={
                "uid": "second",
                "after": first.uid,
                "execution": ExecutionSelection(profile="thread"),
            }
        )
    )
    definition = blueprint_importer.convert(blueprint, program_id="reused", owner=platform.owner)
    assert [step.execution.profile for step in definition.implementation.steps] == [
        "process",
        "thread",
    ]
    assert blueprint.nodes[0].execution.profile == "thread"
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("reused", platform.owner)
    result = await run(platform, revision, GraphState(user_prompt="Placed").model_dump(mode="json"))
    assert result.result["nodes_output"] == {
        first.uid: "Mock echo: Placed",
        "second": "Mock echo: Placed",
    }


@pytest.mark.parametrize("supported", [True, False])
async def test_blueprint_named_environment_preserves_ownership_and_validates_backend(
    platform, application, blueprint_importer, supported
):
    blueprint = resolved_blueprint()
    blueprint.environments = {"workspace": "placed"}
    blueprint.plan[0].execution = ExecutionSelection(environment="workspace")
    definition = blueprint_importer.convert(
        blueprint, program_id="environment", owner=platform.owner
    )
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("environment", platform.owner)
    target = (
        K8sRunnerConfig(image="fixture-receiver:immutable") if supported else ProcessRunnerConfig()
    )
    compiler = ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        {"placed": target},
        "placed",
    )
    context = ExecutionContext(identity=platform.owner)
    if not supported:
        with pytest.raises(ValueError, match="does not support a shared run environment"):
            await compiler.compile(revision, platform.owner, context)
        return
    compiled = await compiler.compile(revision, platform.owner, context)
    assert compiled.environments["workspace"].kind == "owned"
    assert compiled.environments["workspace"].target == target
    payload = ProgramPayload.model_validate(compiled.input)
    prepared = GraphProgramInput.model_validate(
        RunRequest.model_validate(payload.graph_request).input
    )
    assert prepared.targets["respond"] == EnvironmentTarget(name="workspace").model_dump(
        mode="json"
    )


async def test_unapproved_resource_preference_fails_before_dispatch(platform, blueprint_importer):
    blueprint = resolved_blueprint()
    blueprint.nodes[0].execution = ResourceExecutionDefaults(profile="unapproved")
    definition = blueprint_importer.convert(blueprint, program_id="denied", owner=platform.owner)
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("denied", platform.owner)
    with pytest.raises(ValueError, match="not approved: unapproved"):
        await platform.compiler.compile(
            revision, platform.owner, ExecutionContext(identity=platform.owner)
        )


async def test_inline_condition_preference_is_imported_and_runs_in_a_process(
    platform, blueprint_importer
):
    draft = BlueprintDraft.model_validate(
        {
            **resolved_blueprint().model_dump(),
            "conditions": [
                {
                    "rid": "route",
                    "name": "Route",
                    "type": "router_boolean",
                    "config": {"type": "router_boolean", "boolean_value": True},
                    "execution": {"profile": "process"},
                }
            ],
            "plan": [
                {
                    "uid": "respond",
                    "node": "agent",
                    "exit_condition": "route",
                    "branches": {"true": "finish", "false": "finish"},
                },
                {"uid": "finish", "node": "agent", "after": "respond"},
            ],
        }
    )
    resolved = BlueprintResolver(NoExternalResources(), spec_schema=BlueprintSpec).resolve(draft)
    definition = blueprint_importer.convert(resolved, program_id="condition", owner=platform.owner)
    assert definition.implementation.conditions[0].execution.profile == "process"
    await platform.programs.save(definition, platform.owner)
    revision = await platform.programs.publish("condition", platform.owner)
    compiled = await platform.compiler.compile(
        revision, platform.owner, ExecutionContext(identity=platform.owner)
    )
    payload = ProgramPayload.model_validate(compiled.input)
    request = RunRequest.model_validate(payload.graph_request)
    prepared = GraphProgramInput.model_validate(request.input)
    assert prepared.targets["condition_respond"]["runner_type"] == "process"
    result = await run(
        platform, revision, GraphState(user_prompt="condition").model_dump(mode="json")
    )
    assert result.result["nodes_output"] == {
        "respond": "Mock echo: condition",
        "finish": "Mock echo: condition",
    }


@pytest.mark.parametrize("override", [None, {}, {"profile": "thread"}])
def test_blueprint_reference_can_inherit_replace_or_clear_saved_preference(override):
    source = create_autospec(ResourceReader, instance=True)
    agent = Resource(
        rid="catalog-agent",
        identity={"type": "user", "id": "owner"},
        category="nodes",
        type="mock_agent_node",
        name="Agent",
        cfg_dict={"type": "mock_agent_node", "llm": "model"},
        execution=ResourceExecutionDefaults(profile="process"),
    )
    draft = BlueprintDraft.model_validate(resolved_blueprint().model_dump())
    node = {"rid": "$ref:catalog-agent"}
    if override is not None:
        node["execution"] = override
    draft = BlueprintDraft.model_validate(
        {
            **draft.model_dump(),
            "nodes": [node],
            "plan": [{"uid": "respond", "node": "$ref:catalog-agent"}],
        }
    )
    source.get_visible.return_value = agent
    source.resolve_resource.return_value = resolved_blueprint().nodes[0].config
    resolved = BlueprintResolver(source, spec_schema=BlueprintSpec).resolve(draft)
    assert resolved.nodes[0].execution.profile == (
        "process" if override is None else override.get("profile")
    )
    assert agent.execution.profile == "process"
