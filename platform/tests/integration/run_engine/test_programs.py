"""Real local runtime integration for public program contracts and composition."""

import pytest
from support.scenarios import bundle, echo_graph, publish, run

from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.executions.models import StartExecution
from lumora.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
)
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_element_graph_runs_in_real_execution_backend(platform, profile):
    revision = await publish(platform, "echo", echo_graph(profile))
    result = await run(platform, revision, {"name": "world"})
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "greeting:world"}


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_native_async_element_is_awaited_in_real_backend(platform, profile):
    graph = echo_graph(profile)
    graph = graph.model_copy(
        update={
            "resources": tuple(
                resource.model_copy(update={"type_key": "platform_async_echo"})
                if resource.key.rid == "echo"
                else resource
                for resource in graph.resources
            )
        }
    )
    revision = await publish(platform, "async-element", graph)
    result = await run(platform, revision, {"name": "awaited"})
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "greeting:awaited"}


async def test_graph_calls_another_graph_through_explicit_bindings(platform):
    child = await publish(platform, "child", echo_graph())
    parent = await publish(
        platform,
        "parent",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="child",
                    program=child.reference,
                    inputs={"name": PathBinding(path=("input", "name"))},
                    outputs={"output": PathBinding(path=("answer",))},
                ),
            ),
            entry="child",
            exit="child",
            outputs={"answer": PathBinding(path=("output",))},
        ),
    )
    result = await run(platform, parent, {"name": "nested"})
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "greeting:nested"}


async def test_application_program_runs_independently_and_as_graph_step(platform):
    child = await publish(
        platform,
        "application",
        ApplicationDefinition(
            implementation="greeting",
            version="1",
            config={"prefix": "welcome "},
        ),
    )
    direct = await run(platform, child, {"name": "Alice"})
    assert direct.result == {"answer": "welcome Alice"}
    parent = await publish(
        platform,
        "graph",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="app",
                    program=child.reference,
                    inputs={"name": PathBinding(path=("input", "name"))},
                    outputs={"output": PathBinding(path=("answer",))},
                ),
            ),
            entry="app",
            exit="app",
            outputs={"answer": PathBinding(path=("output",))},
        ),
    )
    assert (await run(platform, parent, {"name": "Bob"})).result == {"answer": "welcome Bob"}


async def test_application_program_composes_through_application_runtime_port(platform):
    child = await publish(
        platform, "greeting", ApplicationDefinition(implementation="greeting", version="1")
    )
    parent = await publish(
        platform,
        "composed",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={"greet": child.reference},
        ),
    )
    assert (await run(platform, parent, {"name": "composed"})).result == {
        "answer": "hello composed"
    }


async def test_published_revision_does_not_change_when_draft_changes(platform):
    first = await publish(
        platform, "greeting", ApplicationDefinition(implementation="greeting", version="1")
    )
    second = await publish(
        platform,
        "greeting",
        ApplicationDefinition(
            implementation="greeting",
            version="1",
            config={"prefix": "new "},
        ),
    )
    assert first.revision == 1 and second.revision == 2
    assert (await run(platform, first, {"name": "version"})).result == {"answer": "hello version"}
    assert (await run(platform, second, {"name": "version"})).result == {"answer": "new version"}


async def test_execution_identity_is_idempotent_and_conflicting_inputs_are_refused(platform):
    revision = await publish(
        platform, "greeting", ApplicationDefinition(implementation="greeting", version="1")
    )
    first = await run(platform, revision, {"name": "once"}, "stable")
    repeated = await platform.executions.start(
        StartExecution(
            program=revision.reference,
            inputs={"name": "once"},
            execution_id="stable",
        ),
        platform.owner,
    )
    assert repeated == first
    with pytest.raises(ValueError, match="different request"):
        await platform.executions.start(
            StartExecution(
                program=revision.reference,
                inputs={"name": "twice"},
                execution_id="stable",
            ),
            platform.owner,
        )


async def test_messages_and_cancellation_use_generic_program_contract(platform):
    revision = await publish(
        platform, "waiting", ApplicationDefinition(implementation="waiting", version="1")
    )
    record = await platform.executions.start(
        StartExecution(program=revision.reference), platform.owner
    )
    await platform.executions.send(record.execution_id, "answer", "approved", platform.owner)
    assert (await platform.executions.result(record.execution_id, platform.owner)).result == {
        "answer": "approved"
    }
    another = await platform.executions.start(
        StartExecution(program=revision.reference), platform.owner
    )
    await platform.executions.cancel(another.execution_id, platform.owner)
    assert (
        await platform.executions.result(another.execution_id, platform.owner)
    ).phase == ExecutionPhase.CANCELLED


async def test_other_identity_cannot_observe_or_cancel_execution(platform):
    revision = await publish(
        platform, "greeting", ApplicationDefinition(implementation="greeting", version="1")
    )
    record = await run(platform, revision, {"name": "private"})
    with pytest.raises(PermissionError):
        await platform.executions.cancel(record.execution_id, Identity.user("mallory"))


async def test_application_program_invokes_element_through_application_port(platform):
    revision = await publish(
        platform,
        "invoking",
        ApplicationDefinition(
            implementation="invoking",
            version="1",
            config={"bundle": bundle().model_dump(mode="json")},
        ),
    )
    result = await run(platform, revision, {"name": "application"})
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "middle:application"}


async def test_one_graph_selects_distinct_backends_per_step(platform):
    graph = echo_graph()
    first = graph.steps[0].model_copy(update={"uid": "thread"})
    second = graph.steps[0].model_copy(
        update={
            "uid": "process",
            "execution": ExecutionSelection(profile="process"),
        }
    )
    revision = await publish(
        platform,
        "mixed",
        graph.model_copy(
            update={
                "steps": (first, second),
                "edges": {"thread": ("process",)},
                "entry": "thread",
                "exit": "process",
            }
        ),
    )
    result = await run(platform, revision, {"name": "mixed"})
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "greeting:mixed"}
