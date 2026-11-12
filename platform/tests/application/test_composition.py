"""Composition policy uses application ports and explicit, controllable child lifetimes."""

import asyncio
from unittest.mock import create_autospec

import pytest

from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.composition.models import (
    ChooseConfig,
    MapConfig,
    RepeatConfig,
    WaitConfig,
)
from lumora.programs.composition.programs import (
    COORDINATORS,
    CompositionContractError,
    choose_program,
    map_program,
    repeat_program,
    wait_program,
)
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition
from lumora.programs.ports import ChildExecution, ProgramRuntime
from lumora.programs.service import ProgramContractError


@pytest.fixture
def runtime():
    return create_autospec(ProgramRuntime, instance=True)


async def test_map_bounds_active_children_preserves_input_order_and_has_stable_keys(runtime):
    active = maximum = 0
    started = []

    async def start(name, inputs, *, key):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        started.append((key, inputs["index"]))
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = key

        async def result():
            nonlocal active
            await asyncio.sleep((5 - inputs["index"]) * 0.001)
            active -= 1
            return inputs["item"]

        child.result.side_effect = result
        return child

    runtime.start_child.side_effect = start
    output = await map_program(
        runtime, {"items": ["a", "b", "c", "d", "e"]}, MapConfig(concurrency=2)
    )
    assert maximum == 2
    assert [value["value"] for value in output["items"]] == ["a", "b", "c", "d", "e"]
    assert sorted(started) == [(f"item-{i}", i) for i in range(5)]


async def test_map_rejects_item_overflow_before_dispatch_and_accepts_empty_input(runtime):
    with pytest.raises(CompositionContractError):
        await map_program(runtime, {"items": [1, 2]}, MapConfig(max_items=1))
    assert await map_program(runtime, {"items": []}, MapConfig()) == {"items": []}
    runtime.start_child.assert_not_awaited()


@pytest.mark.parametrize("cancel", [False, True])
async def test_map_failure_or_parent_cancellation_cancels_owned_calls_and_drains_tasks(
    runtime, cancel
):
    children = []
    both = asyncio.Event()

    async def start(name, inputs, *, key):
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = key
        children.append(child)
        if len(children) == 2:
            both.set()

        async def result():
            await both.wait()
            if inputs["index"] == 0 and not cancel:
                raise ValueError("child failed")
            await asyncio.Event().wait()

        child.result.side_effect = result
        return child

    runtime.start_child.side_effect = start
    task = asyncio.create_task(map_program(runtime, {"items": [1, 2, 3]}, MapConfig(concurrency=2)))
    await both.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else ValueError):
        await task
    assert len(children) == 2
    assert all(child.cancel.await_count == 1 for child in children)
    assert all(child.result.await_count == 1 for child in children)


@pytest.mark.parametrize("bound,reason,count", [(5, "satisfied", 3), (2, "limit_reached", 2)])
async def test_repeat_threads_recorded_state_and_reports_bound_exhaustion(
    runtime, bound, reason, count
):
    async def start(name, inputs, *, key):
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = key
        child.result.return_value = {"state": inputs["state"] + 1, "done": inputs["state"] + 1 == 3}
        return child

    runtime.start_child.side_effect = start
    output = await repeat_program(runtime, {"state": 0}, RepeatConfig(max_iterations=bound))
    assert output["reason"] == reason and output["iterations"] == count and output["state"] == count
    assert [call.kwargs["key"] for call in runtime.start_child.await_args_list] == [
        f"iteration-{i}" for i in range(count)
    ]


async def test_repeat_requires_a_boolean_predicate_not_truthiness(runtime):
    child = create_autospec(ChildExecution, instance=True)
    child.execution_id = "child"
    child.result.return_value = {"state": 1, "done": "false"}
    runtime.start_child.return_value = child
    with pytest.raises(CompositionContractError, match="boolean"):
        await repeat_program(runtime, {"state": 0}, RepeatConfig())


async def test_choose_admits_exactly_one_declared_branch_and_hides_unknown_values(runtime):
    child = create_autospec(ChildExecution, instance=True)
    child.execution_id = "child"
    child.result.return_value = {"answer": "chosen"}
    runtime.start_child.return_value = child
    config = ChooseConfig(branches={"approved": "apply", "rejected": "repair"})
    output = await choose_program(runtime, {"choice": "approved"}, config)
    assert output["branch"] == "approved" and output["value"] == {"answer": "chosen"}
    runtime.start_child.assert_awaited_once_with("apply", {"choice": "approved"}, key="selected")
    with pytest.raises(CompositionContractError) as error:
        await choose_program(runtime, {"choice": "private-invalid-value"}, config)
    assert "private-invalid-value" not in str(error.value)


@pytest.mark.parametrize("timeout", [False, True])
async def test_wait_uses_runtime_deadlines_and_keeps_timeout_distinct_from_event(runtime, timeout):
    if timeout:
        runtime.receive.side_effect = TimeoutError()
    else:
        runtime.receive.return_value = {"event": 1}
    output = await wait_program(runtime, {}, WaitConfig(channel="answer", timeout_seconds=2))
    assert output == {
        "reason": "timed_out" if timeout else "received",
        "value": None if timeout else {"event": 1},
    }
    runtime.receive.assert_awaited_once_with("answer", timeout=2)


async def test_missing_composition_children_fail_before_publication(application):
    from_missing = ProgramDefinition(
        program_id="invalid",
        name="invalid",
        owner=application.owner,
        implementation=CustomCoordinatorDefinition(implementation="map", version="1", config={}),
    )
    for registration in COORDINATORS:
        application.applications.register(registration)
    draft = await application.programs.save(from_missing, application.owner)
    with pytest.raises(ProgramContractError) as refused:
        await application.programs.publish(
            from_missing.program_id, application.owner, expected_version=draft.version
        )
    assert refused.value.issue.code == ProgramIssueCode.BINDING
    assert refused.value.issue.path == ("implementation", "children", "body")
