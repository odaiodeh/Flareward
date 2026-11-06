"""Actual UnifAI coordination, child runs, bindings, and history replay on Temporal."""

import asyncio

import pytest
from mas.application.execution.models import StartExecution
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
)
from runengine.adapters.coordination.temporal.host import TemporalRunHost
from runengine.adapters.coordination.temporal.models import TemporalRunIdentity
from support.scenarios import echo_graph, publish
from support.temporal import replay
from temporalio.api.enums.v1 import EventType

from bootstrap.worker import compose_worker


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_graph_application_graph_composition_and_replay(durable, application, profile):
    leaf = await publish(application, "leaf", echo_graph(profile))
    middle = await publish(
        application,
        "middle",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={"greet": leaf.reference},
        ),
    )
    parent = await publish(
        application,
        "parent",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="middle",
                    program=middle.reference,
                    inputs={"name": PathBinding(path=("user_prompt",))},
                    outputs={"output": PathBinding(path=("answer",))},
                ),
            ),
            entry="middle",
            exit="middle",
            inputs={"user_prompt": PathBinding(path=("name",))},
            outputs={"answer": PathBinding(path=("output",))},
        ),
    )
    async with compose_worker(durable.settings):
        record = await durable.executions.start(
            StartExecution(program=parent.reference, inputs={"name": "durable"}),
            application.owner,
        )
        async with asyncio.timeout(20):
            result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert result.result == {"answer": "greeting:durable"}
        runs = [record.engine_handle]
        for run_id in runs:
            history = await durable.client.get_workflow_handle(run_id).fetch_history()
            runs.extend(
                event.start_child_workflow_execution_initiated_event_attributes.workflow_id
                for event in history.events
                if event.event_type == EventType.EVENT_TYPE_START_CHILD_WORKFLOW_EXECUTION_INITIATED
            )
            await replay(durable.client, durable.settings, run_id)
        assert len(runs) == 3
        children = await durable.executions.children(record.execution_id, application.owner)
        grand = await durable.executions.children(children[0].execution_id, application.owner)
        assert [record.engine_handle, children[0].engine_handle, grand[0].engine_handle] == runs
        assert children[0].program == middle.reference and grand[0].program == leaf.reference
        assert grand[0].inputs == {"name": "durable"}
        assert all(value.phase == ExecutionPhase.COMPLETED for value in (*children, *grand))
        assert grand[0].context.ancestor_execution_ids == (
            record.execution_id,
            children[0].execution_id,
        )
        host = TemporalRunHost(durable.settings.host, client=durable.client)
        description = await durable.client.get_workflow_handle(record.engine_handle).describe()
        pinned = await host.get_pinned_handle(
            TemporalRunIdentity(
                namespace=description.namespace,
                workflow_id=description.id,
                run_id=description.run_id,
            )
        )
        assert [child.run_id for child in await pinned.children()] == [children[0].engine_handle]
        for child, parent_id in (
            (children[0], record.engine_handle),
            (grand[0], children[0].engine_handle),
        ):
            handle = await host.get_handle(child.engine_handle)
            assert (await handle.status()).parent_run_id == parent_id
