"""Kill real native workers and recover through persisted Temporal history and runtime ports."""

import asyncio

from support.recovery import effect_counts
from support.scenarios import publish, resource
from support.temporal import replay, worker_process
from temporalio.api.enums.v1 import EventType, TimeoutType

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.models import StartExecution
from lumora.programs.domain.models import ApplicationDefinition
from lumora.resources.domain.categories import ResourceCategory


async def test_killed_invocation_is_redelivered_without_repeating_business_effect(
    durable, application, tmp_path
):
    committed, release, database = (
        tmp_path / name for name in ("committed", "release", "effect.db")
    )
    effect = resource(
        "effect",
        category=ResourceCategory.NODE,
        type_key="platform_effect",
        config={
            "database": str(database),
            "committed": str(committed),
            "release": str(release),
            "operation_key": "one-effect",
        },
    )
    bundle = ElementBundleResolver(application.elements).resolve(effect.key, (effect,))
    revision = await publish(
        application,
        "recovering",
        ApplicationDefinition(
            implementation="recovery",
            version="1",
            config={"bundle": bundle.model_dump(mode="json")},
        ),
    )
    async with worker_process(durable.settings, tmp_path / "first.log") as first:
        try:
            record = await durable.executions.start(
                StartExecution(program=revision.reference), application.owner
            )
            async with asyncio.timeout(20):
                while not committed.exists():
                    first.assert_running()
                    current = await durable.executions.refresh(
                        record.execution_id, application.owner
                    )
                    assert current.phase == ExecutionPhase.RUNNING, current.failure
                    await asyncio.sleep(0.02)
            await first.crash()
        finally:
            release.touch()
    effects, pids = await asyncio.to_thread(effect_counts, database)
    assert effects == len(pids) == 1
    assert (await durable.executions.refresh(record.execution_id, application.owner)).phase == (
        ExecutionPhase.RUNNING
    )
    async with worker_process(durable.settings, tmp_path / "replacement.log") as replacement:
        async with asyncio.timeout(30):
            result = await durable.executions.result(record.execution_id, application.owner)
        replacement.assert_running()
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert result.result == {"answer": "committed"}
        history = await durable.client.get_workflow_handle(record.engine_handle).fetch_history()
        attempts = [
            event.activity_task_started_event_attributes
            for event in history.events
            if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_STARTED
        ]
        assert any(
            attempt.attempt == 2
            and attempt.last_failure.timeout_failure_info.timeout_type
            == TimeoutType.TIMEOUT_TYPE_HEARTBEAT
            for attempt in attempts
        )
        await replay(durable.client, durable.settings, record.engine_handle)
    effects, pids = await asyncio.to_thread(effect_counts, database)
    assert effects == 1 and len(pids) == len(set(pids)) == 2


async def test_message_wait_survives_worker_restart(durable, application, tmp_path):
    revision = await publish(
        application,
        "waiting",
        ApplicationDefinition(
            implementation="waiting",
            version="1",
        ),
    )
    async with worker_process(durable.settings, tmp_path / "waiting.log") as first:
        record = await durable.executions.start(
            StartExecution(program=revision.reference), application.owner
        )
        async with asyncio.timeout(20):
            while True:
                first.assert_running()
                history = await durable.client.get_workflow_handle(
                    record.engine_handle
                ).fetch_history()
                if any(
                    event.event_type == EventType.EVENT_TYPE_WORKFLOW_TASK_COMPLETED
                    for event in history.events
                ):
                    break
                await asyncio.sleep(0.02)
        assert (await durable.executions.refresh(record.execution_id, application.owner)).phase == (
            ExecutionPhase.RUNNING
        )
        await first.crash()
    async with worker_process(durable.settings, tmp_path / "resumed.log") as replacement:
        async with asyncio.timeout(20):
            await durable.executions.send(
                record.execution_id, "answer", "resumed", application.owner
            )
            result = await durable.executions.result(record.execution_id, application.owner)
        replacement.assert_running()
        assert result.phase == ExecutionPhase.COMPLETED and result.result == {"answer": "resumed"}
        await replay(durable.client, durable.settings, record.engine_handle)
