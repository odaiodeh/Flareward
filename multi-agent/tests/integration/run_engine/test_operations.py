"""Real thread/process execution of one operation from graphs and application programs."""

import pytest
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramCallStep,
)
from support.operations import AliasedTextSpec, operation_bundle, operation_graph
from support.scenarios import publish, run


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_typed_operation_runs_from_graph_with_explicit_bindings(platform, profile):
    revision = await publish(platform, "typed-graph", operation_graph(profile))
    result = await run(platform, revision, {"name": "graph"})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == {"answer": "typed:middle:graph"}


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_same_operation_runs_from_code_program_nested_in_graph(
    platform, application, profile
):
    definition = ApplicationDefinition(
        implementation="typed_operation",
        version="1",
        config={"bundle": operation_bundle(application.elements).model_dump(mode="json")},
    )
    child = await publish(platform, "typed-code", definition)
    draft = child.definition.model_copy(update={"execution_profile": profile})
    await platform.programs.save(draft, platform.owner, expected_version=1)
    child = await platform.programs.publish(
        draft.program_id,
        platform.owner,
        expected_version=(await platform.programs.draft(draft.program_id, platform.owner)).version,
    )
    direct = await run(platform, child, {"name": "direct"})
    assert direct.phase == ExecutionPhase.COMPLETED, direct.failure
    assert direct.result == {"answer": "typed:middle:direct"}
    parent = await publish(
        platform,
        "typed-parent",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="child",
                    program=child.reference,
                    inputs={"name": PathBinding(path=("user_prompt",))},
                    outputs={"output": PathBinding(path=("answer",))},
                ),
            ),
            entry="child",
            exit="child",
            inputs={"user_prompt": PathBinding(path=("name",))},
            outputs={"answer": PathBinding(path=("output",))},
        ),
    )
    result = await run(platform, parent, {"name": "nested"})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == {"answer": "typed:middle:nested"}
    children = await platform.executions.children(result.execution_id, platform.owner)
    assert len(children) == 1 and children[0].program == child.reference


async def test_operation_request_contract_failure_is_a_failed_execution(platform):
    graph = operation_graph()
    step = OperationStep.model_validate(
        {
            **graph.steps[0].model_dump(mode="json"),
            "inputs": {"text": PathBinding(path=("values", "text")).model_dump(mode="json")},
        }
    )
    revision = await publish(
        platform,
        "invalid-request",
        graph.model_copy(update={"steps": (step,), "inputs": {"values": PathBinding(path=())}}),
    )
    result = await run(platform, revision, {"text": {"private": "invalid"}})
    assert result.phase == ExecutionPhase.FAILED
    assert result.failure is not None and "input violates" in result.failure.message
    assert "private" not in result.failure.message


async def test_operation_binding_cannot_write_an_unknown_graph_channel(platform):
    graph = operation_graph()
    step = graph.steps[0].model_copy(update={"outputs": {"unknown": PathBinding(path=())}})
    revision = await publish(
        platform, "invalid-binding", graph.model_copy(update={"steps": (step,)})
    )
    with pytest.raises(ValueError, match="unknown state channels"):
        await run(platform, revision, {"name": "request"})


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("alias", ["text", "textAlias", "payload"])
async def test_binding_admission_preserves_real_operation_input_aliases(
    application, platform, profile, alias
):
    application.elements.register_spec_class(AliasedTextSpec)
    graph = operation_graph(profile)
    operation = graph.resources[0].model_copy(update={"type_key": AliasedTextSpec.type_key})
    step = graph.steps[0].model_copy(
        update={
            "inputs": {
                alias: PathBinding(path=("values",))
                if alias == "payload"
                else PathBinding(path=("user_prompt",))
            }
        }
    )
    graph = graph.model_copy(
        update={
            "resources": (operation, *graph.resources[1:]),
            "steps": (step,),
            "inputs": {
                "user_prompt": PathBinding(path=("name",)),
                "values": PathBinding(path=("payload",)),
            },
        }
    )
    revision = await publish(platform, "aliased", graph)
    result = await run(platform, revision, {"name": "aliased", "payload": {"text": "aliased"}})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == {"answer": "typed:middle:aliased"}
