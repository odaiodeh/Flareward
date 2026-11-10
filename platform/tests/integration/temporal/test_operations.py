"""Typed calls survive portable worker delivery and native history replay."""

import asyncio

import pytest
from support.operations import operation_bundle, operation_graph
from support.scenarios import publish
from support.temporal import replay, worker_process

from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.models import StartExecution
from lumora.programs.domain.models import ApplicationDefinition


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_code_program_calls_typed_operation_graph_and_replays(
    durable, application, profile, tmp_path
):
    child = await publish(application, "typed-graph", operation_graph(profile))
    parent = await publish(
        application,
        "typed-parent",
        ApplicationDefinition(
            implementation="composed", version="1", children={"greet": child.reference}
        ),
    )
    async with worker_process(durable.settings, tmp_path / "operation-worker.log"):
        record = await durable.executions.start(
            StartExecution(program=parent.reference, inputs={"name": "durable"}), application.owner
        )
        async with asyncio.timeout(30):
            result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert result.result == {"answer": "typed:middle:durable"}
        children = await durable.executions.children(record.execution_id, application.owner)
        assert len(children) == 1 and children[0].program == child.reference
        for execution in (result, *children):
            await replay(durable.client, durable.settings, execution.engine_handle)


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_code_program_invokes_typed_operation_directly_and_replays(
    durable, application, profile, tmp_path
):
    definition = ApplicationDefinition(
        implementation="typed_operation",
        version="1",
        config={"bundle": operation_bundle(application.elements).model_dump(mode="json")},
    )
    first = await publish(application, "typed-direct", definition)
    await application.programs.save(
        first.definition.model_copy(update={"execution_profile": profile}),
        application.owner,
        expected_version=1,
    )
    revision = await application.programs.publish(
        "typed-direct",
        application.owner,
        expected_version=(
            await application.programs.draft("typed-direct", application.owner)
        ).version,
    )
    async with worker_process(durable.settings, tmp_path / "operation-worker.log"):
        record = await durable.executions.start(
            StartExecution(program=revision.reference, inputs={"name": "direct"}), application.owner
        )
        async with asyncio.timeout(30):
            result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert result.result == {"answer": "typed:middle:direct"}
        await replay(durable.client, durable.settings, result.engine_handle)
