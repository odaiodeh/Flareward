"""Compilation keeps owned source identity, placement inheritance and explicit imports."""

import pytest
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import ApplicationDefinition, ProgramBody, ProgramRevision
from outbound.run_engine.compiler import ProgramCompiler
from run_engine.models import ProgramPayload
from runengine.coordination.models import RunRequest
from runengine.invocation.config import K8sRunnerConfig, ProcessRunnerConfig, ThreadRunnerConfig
from support.operations import operation_graph
from support.scenarios import publish


@pytest.fixture
def compiler(application):
    return ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        {
            "thread": ThreadRunnerConfig(),
            "process": ProcessRunnerConfig(),
            "sandbox": K8sRunnerConfig(image="unifai-receiver:fixture"),
        },
        "thread",
    )


@pytest.mark.parametrize(
    "target_kind,override,expected",
    [
        ("owned", None, "process"),
        ("owned", "thread", "thread"),
        ("published", None, "thread"),
        ("published", "process", "process"),
    ],
)
async def test_owned_default_inherits_but_published_default_is_independent(
    application, compiler, target_kind, override, expected
):
    implementation = ApplicationDefinition(implementation="greeting", version="1")
    if target_kind == "owned":
        target = ProgramBody(implementation=implementation, execution_profile=override)
    else:
        child = await publish(application, "child", implementation, execution_profile=override)
        target = child.reference
    root = await publish(
        application,
        "root",
        ApplicationDefinition(implementation="composed", version="1", children={"greet": target}),
        execution_profile="process",
    )
    request = await compiler.compile(
        root, application.owner, ExecutionContext(identity=application.owner)
    )
    payload = ProgramPayload.model_validate(request.input)
    child_payload = ProgramPayload.model_validate(
        RunRequest.model_validate(payload.children["greet"]).input
    )
    assert payload.placement.default_profile == "process"
    assert child_payload.placement.default_profile == expected
    assert child_payload.body_path == (("greet",) if target_kind == "owned" else ())
    assert child_payload.program == (root.reference if target_kind == "owned" else child.reference)
    assert "revision" not in child_payload.model_dump()


@pytest.mark.parametrize("imported", [True, False])
async def test_containment_does_not_grant_parent_environment(application, compiler, imported):
    graph = operation_graph().model_copy(
        update={
            "steps": tuple(
                step.model_copy(update={"execution": ExecutionSelection(environment="workspace")})
                for step in operation_graph().steps
            )
        }
    )
    root = await publish(
        application,
        "root",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            environments={"parent": "sandbox"},
            children={"greet": ProgramBody(implementation=graph)},
            child_environment_imports={"greet": {"workspace": "parent"}} if imported else {},
        ),
    )
    context = ExecutionContext(identity=application.owner)
    if not imported:
        with pytest.raises(ValueError, match="Undeclared environment"):
            await compiler.compile(root, application.owner, context)
        return
    request = await compiler.compile(root, application.owner, context)
    payload = ProgramPayload.model_validate(request.input)
    child = RunRequest.model_validate(payload.children["greet"])
    assert request.environments["parent"].kind == "owned"
    assert not child.environments
    child_payload = ProgramPayload.model_validate(child.input)
    assert child_payload.placement.environments == ("workspace",)
    assert payload.placement.child_imports == {"greet": {"workspace": "parent"}}
    summary = payload.placement.summary
    assert summary.program == root.reference
    assert summary.environments == {"parent": "sandbox"}
    assert summary.dynamic_invocations
    child_summary = summary.children["greet"]
    assert child_summary.environment_imports == {"workspace": "parent"}
    assert child_summary.program.body_path == ("greet",)
    assert child_summary.program.imported_environments == ("workspace",)
    assert not child_summary.program.dynamic_invocations
    invocation = child_summary.program.invocations[0]
    assert invocation.step_uid == "typed-work"
    assert invocation.environment == "workspace" and invocation.profile is None


async def test_restored_revision_rechecks_bindings_before_native_preparation(application, compiler):
    original = await publish(application, "root", operation_graph())
    graph = original.definition.implementation
    step = graph.steps[0].model_copy(update={"inputs": {}})
    restored = ProgramRevision(
        definition=original.definition.model_copy(
            update={"implementation": graph.model_copy(update={"steps": (step,)})}
        ),
        revision=original.revision,
    )
    with pytest.raises(ValueError, match="Required invocation input"):
        await compiler.compile(
            restored, application.owner, ExecutionContext(identity=application.owner)
        )
