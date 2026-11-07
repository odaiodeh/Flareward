"""Core composition calls real graph/operation/code children through the same engine."""

import pytest
from mas.application.execution.models import StartExecution
from mas.application.programs.composition.programs import APPLICATION_PROGRAMS
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramCallStep,
)
from support.composition import APPLICATION_PROGRAMS as FIXTURE_PROGRAMS
from support.composition import composition_graph, mapped_program, repeated_program
from support.operations import operation_graph
from support.scenarios import publish, run


@pytest.fixture
def composition(application):
    for registration in (*APPLICATION_PROGRAMS, *FIXTURE_PROGRAMS):
        application.applications.register(registration)


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_graph_map_graph_operation_preserves_pinned_calls_order_and_occurrences(
    platform, profile
):
    body = await publish(platform, "body", operation_graph(profile))
    mapped = await publish(platform, "mapped", mapped_program(body.reference))
    root = await publish(platform, "root", composition_graph(mapped.reference))
    changed = operation_graph(profile).model_copy(
        update={"outputs": {"answer": LiteralBinding(value="edited")}}
    )
    assert (await publish(platform, "body", changed)).revision == 2
    result = await run(platform, root, {"items": ["one", "two", "three"]})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    items = result.result["result"]["items"]
    assert [item["value"]["answer"] for item in items] == [
        "typed:middle:one",
        "typed:middle:two",
        "typed:middle:three",
    ]
    child = (await platform.executions.children(result.execution_id, platform.owner))[0]
    grandchildren = await platform.executions.children(child.execution_id, platform.owner)
    assert {item["execution_id"] for item in items} == {
        record.execution_id for record in grandchildren
    }
    assert all(
        record.program == body.reference and record.context.root_execution_id == result.execution_id
        for record in grandchildren
    )


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_owned_graph_map_graph_operation_needs_only_one_publication(platform, profile):
    body = ProgramBody(implementation=operation_graph(profile))
    control = ProgramBody(implementation=mapped_program(body))
    root = await publish(platform, "owned", composition_graph(control))
    result = await run(platform, root, {"items": ["one", "two", "three"]})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    items = result.result["result"]["items"]
    assert [item["value"]["answer"] for item in items] == [
        "typed:middle:one",
        "typed:middle:two",
        "typed:middle:three",
    ]
    assert result.content_digest == root.content_digest and result.body_path == ()
    mapped = (await platform.executions.children(result.execution_id, platform.owner))[0]
    assert mapped.program == root.reference and mapped.body_path == ("compose",)
    assert mapped.content_digest == root.content_digest
    children = await platform.executions.children(mapped.execution_id, platform.owner)
    assert {item["execution_id"] for item in items} == {child.execution_id for child in children}
    assert len(children) == 3
    assert all(
        child.program == root.reference
        and child.body_path == ("compose", "body")
        and child.content_digest == root.content_digest
        and child.context.root_execution_id == result.execution_id
        and child.context.parent_execution_id == mapped.execution_id
        for child in children
    )
    library = await platform.programs.list(platform.owner)
    assert [item.program_id for item in library.programs] == ["owned"]


@pytest.mark.usefixtures("composition")
async def test_published_boundary_resets_owned_source_address(platform):
    greeting = ProgramBody(
        implementation=ApplicationDefinition(implementation="greeting", version="1")
    )
    leaf = await publish(
        platform,
        "reusable",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="greet",
                    program=greeting,
                    inputs={"name": PathBinding(path=("input", "name"))},
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            entry="greet",
            exit="greet",
            outputs={"answer": PathBinding(path=("values",))},
        ),
    )
    root = await publish(
        platform,
        "caller",
        composition_graph(ProgramBody(implementation=mapped_program(leaf.reference))),
    )
    result = await run(platform, root, {"items": ["one"]})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    mapped = (await platform.executions.children(result.execution_id, platform.owner))[0]
    child = (await platform.executions.children(mapped.execution_id, platform.owner))[0]
    nested = (await platform.executions.children(child.execution_id, platform.owner))[0]
    assert mapped.program == root.reference and mapped.body_path == ("compose",)
    assert child.program == leaf.reference and child.body_path == ()
    assert nested.program == leaf.reference and nested.body_path == ("greet",)
    assert child.content_digest == nested.content_digest == leaf.content_digest
    assert nested.result == result.result["result"]["items"][0]["value"]["answer"]


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("bound,reason,count", [(5, "satisfied", 3), (2, "limit_reached", 2)])
async def test_repeat_owns_its_body_and_records_distinct_iterations(platform, bound, reason, count):
    root = await publish(
        platform,
        "owned-repeat",
        repeated_program(
            ProgramBody(
                implementation=ApplicationDefinition(
                    implementation="composition_counter", version="1"
                )
            ),
            bound=bound,
        ),
    )
    result = await run(platform, root, {"state": 0})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result["reason"] == reason and result.result["state"] == count
    children = await platform.executions.children(result.execution_id, platform.owner)
    assert len(children) == count and len({child.execution_id for child in children}) == count
    assert all(
        child.body_path == ("body",) and child.program == root.reference for child in children
    )
    assert {child.inputs["iteration"] for child in children} == set(range(count))


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("bound,reason,count", [(5, "satisfied", 3), (2, "limit_reached", 2)])
async def test_repeat_reuses_a_pinned_body_and_has_distinct_iteration_children(
    platform, bound, reason, count
):
    body = await publish(
        platform,
        "counter",
        ApplicationDefinition(implementation="composition_counter", version="1"),
    )
    repeat = await publish(platform, "repeat", repeated_program(body.reference, bound=bound))
    result = await run(platform, repeat, {"state": 0})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result["reason"] == reason and result.result["state"] == count
    children = await platform.executions.children(result.execution_id, platform.owner)
    assert len(children) == count and len({child.execution_id for child in children}) == count
    assert {child.inputs["iteration"] for child in children} == set(range(count))


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("choice", ["approved", "rejected", "private-unknown"])
@pytest.mark.parametrize("owned", [False, True])
async def test_choose_starts_only_the_recorded_declared_branch(platform, choice, owned):
    implementation = ApplicationDefinition(implementation="greeting", version="1")
    target = (
        ProgramBody(implementation=implementation)
        if owned
        else (await publish(platform, "body", implementation)).reference
    )
    choose = await publish(
        platform,
        "choose",
        ApplicationDefinition(
            implementation="choose",
            version="1",
            config={"branches": {"approved": "apply", "rejected": "repair"}},
            children={"apply": target, "repair": target},
        ),
    )
    result = await run(platform, choose, {"choice": choice, "name": "chosen"})
    children = await platform.executions.children(result.execution_id, platform.owner)
    if choice == "private-unknown":
        assert result.phase == ExecutionPhase.FAILED and result.failure.kind == "contract"
        assert not children and choice not in result.failure.message
    else:
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert result.result["branch"] == choice and len(children) == 1
        assert children[0].body_path == (
            ("apply" if choice == "approved" else "repair",) if owned else ()
        )


@pytest.mark.parametrize("boundary", ["input", "output"])
async def test_owned_body_enforces_its_own_interface_without_echoing_values(platform, boundary):
    schema = {
        "type": "object",
        "properties": {"name" if boundary == "input" else "answer": {"type": "integer"}},
    }
    body = ProgramBody(
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
        **{f"{boundary}_schema": schema},
    )
    root = await publish(
        platform,
        "contract",
        ApplicationDefinition(implementation="composed", version="1", children={"greet": body}),
    )
    result = await run(platform, root, {"name": "private-contract-value"})
    assert result.phase == ExecutionPhase.FAILED
    child = (await platform.executions.children(result.execution_id, platform.owner))[0]
    assert child.phase == ExecutionPhase.FAILED
    assert child.failure.kind == "contract"
    assert f"Program {boundary} violates its contract" in child.failure.message
    assert "private-contract-value" not in child.failure.message
    assert "private-contract-value" not in result.failure.message


@pytest.mark.usefixtures("composition")
async def test_owned_wait_suspends_and_resumes_through_existing_native_child(platform):
    root = await publish(
        platform,
        "owned-wait",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={
                "greet": ProgramBody(
                    implementation=ApplicationDefinition(
                        implementation="wait",
                        version="1",
                        config={"channel": "answer", "timeout_seconds": 0.02},
                    )
                )
            },
        ),
    )
    result = await run(platform, root, {})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result["reason"] == "timed_out"
    child = (await platform.executions.children(result.execution_id, platform.owner))[0]
    assert child.body_path == ("greet",) and child.content_digest == root.content_digest


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("timeout", [False, True])
async def test_wait_uses_native_message_or_deadline_without_an_element_invocation(
    platform, timeout
):
    wait = await publish(
        platform,
        "wait",
        ApplicationDefinition(
            implementation="wait",
            version="1",
            config={"channel": "answer", "timeout_seconds": 0.02 if timeout else 5},
        ),
    )
    record = await platform.executions.start(StartExecution(program=wait.reference), platform.owner)
    if not timeout:
        await platform.executions.send(record.execution_id, "answer", {"value": 1}, platform.owner)
    result = await platform.executions.result(record.execution_id, platform.owner)
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result["reason"] == ("timed_out" if timeout else "received")
