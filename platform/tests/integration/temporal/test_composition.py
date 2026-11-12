"""Bounded composition uses real Temporal children/invocations and native replay."""

import asyncio

import pytest
from support.composition import COORDINATORS as FIXTURE_PROGRAMS
from support.composition import composition_graph, mapped_program, repeated_program
from support.operations import operation_graph
from support.scenarios import publish
from support.temporal import replay, worker_process, workflow_handle

from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.models import StartExecution
from lumora.programs.composition.programs import COORDINATORS
from lumora.programs.domain.models import CustomCoordinatorDefinition


@pytest.fixture
def composition(application):
    for registration in (*COORDINATORS, *FIXTURE_PROGRAMS):
        application.applications.register(registration)


async def replay_tree(durable, application, settings, execution_id):
    record = await durable.executions.refresh(execution_id, application.owner)
    await replay(durable.client, settings, record.engine_handle)
    children = await durable.executions.children(execution_id, application.owner)
    for child in children:
        await replay_tree(durable, application, settings, child.execution_id)


@pytest.mark.usefixtures("composition")
@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_graph_map_graph_operation_replays_all_children(
    durable, application, tmp_path, profile
):
    body = await publish(application, "body", operation_graph(profile))
    mapped = await publish(application, "mapped", mapped_program(body.reference))
    root = await publish(application, "root", composition_graph(mapped.reference))
    async with worker_process(durable.settings, tmp_path / "worker.log"):
        record = await durable.executions.start(
            StartExecution(program=root.reference, inputs={"items": ["first", "second", "third"]}),
            application.owner,
        )
        async with asyncio.timeout(30):
            result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        items = result.result["result"]["items"]
        assert [value["value"]["answer"] for value in items] == [
            "typed:middle:first",
            "typed:middle:second",
            "typed:middle:third",
        ]
        mapped_record = (await durable.executions.children(record.execution_id, application.owner))[
            0
        ]
        children = await durable.executions.children(mapped_record.execution_id, application.owner)
        assert {item["execution_id"] for item in items} == {
            child.execution_id for child in children
        }
        await replay_tree(durable, application, durable.settings, record.execution_id)


@pytest.mark.usefixtures("composition")
async def test_nested_map_repeat_and_durable_wait_survive_worker_restart(
    durable, application, tmp_path
):
    settings = durable.settings.model_copy(
        update={
            "application_modules": (*durable.settings.application_modules, "support.composition")
        }
    )
    body = await publish(
        application,
        "counter",
        CustomCoordinatorDefinition(implementation="composition_counter", version="1"),
    )
    repeated = await publish(application, "repeated", repeated_program(body.reference))
    definition = mapped_program(repeated.reference).model_copy(
        update={
            "config": {"concurrency": 2, "inputs": {"state": {"kind": "path", "path": ["item"]}}}
        }
    )
    mapped = await publish(application, "mapped", definition)
    wait = await publish(
        application,
        "wait",
        CustomCoordinatorDefinition(
            implementation="wait", version="1", config={"channel": "answer", "timeout_seconds": 30}
        ),
    )
    async with worker_process(settings, tmp_path / "before-worker.log"):
        pending = await durable.executions.start(
            StartExecution(program=wait.reference), application.owner
        )
        async with asyncio.timeout(10):
            while True:
                history = await workflow_handle(
                    durable.client, pending.engine_handle
                ).fetch_history()
                if any(
                    event.HasField("timer_started_event_attributes") for event in history.events
                ):
                    break
                await asyncio.sleep(0.05)
    async with worker_process(settings, tmp_path / "after-worker.log"):
        await durable.executions.send(
            pending.execution_id, "answer", {"recorded": True}, application.owner
        )
        result = await durable.executions.result(pending.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED and result.result["reason"] == "received"
        record = await durable.executions.start(
            StartExecution(program=mapped.reference, inputs={"items": [0, 1, 2]}), application.owner
        )
        result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        items = result.result["items"]
        assert [item["value"]["iterations"] for item in items] == [3, 2, 1]
        assert all(item["value"]["reason"] == "satisfied" for item in items)
        await replay_tree(durable, application, settings, record.execution_id)
        await replay_tree(durable, application, settings, pending.execution_id)
