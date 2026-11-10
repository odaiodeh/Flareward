"""Infrastructure support owns native worker processes and replays recorded history."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from importlib import import_module
from pathlib import Path

from runengine.adapters.coordination.temporal.models import TemporalRunIdentity
from runengine.adapters.coordination.temporal.workflow import CoordinationWorkflow
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client, WorkflowHandle
from temporalio.worker import Replayer
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.bootstrap.worker import workflow_modules
from support.processes import OwnedProcess, command_process, settings_environment


def workflow_handle(client: Client, run_id: str) -> WorkflowHandle:
    """Resolve either a plain root identity or an encoded native execution identity."""
    identity = TemporalRunIdentity.decode(run_id)
    return (
        client.get_workflow_handle(identity.workflow_id, run_id=identity.run_id)
        if identity is not None
        else client.get_workflow_handle(run_id)
    )


async def replay(client: Client, settings: WorkerSettings, run_id: str) -> None:
    modules = workflow_modules(settings)
    for name in modules:
        import_module(name)
    history = await workflow_handle(client, run_id).fetch_history()
    await Replayer(
        namespace=settings.host.namespace,
        workflows=[CoordinationWorkflow],
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_modules("runengine", *modules)
        ),
    ).replay_workflow(history)


@asynccontextmanager
async def worker_process(
    settings: WorkerSettings,
    log: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> AsyncIterator[OwnedProcess]:
    configuration = settings_environment(settings)
    if environment is not None:
        configuration.update(environment)
    async with command_process(
        ["-m", "lumora.bootstrap.http_cli", "worker"], configuration, log
    ) as worker:
        client = await Client.connect(settings.host.endpoint, namespace=settings.host.namespace)
        async with asyncio.timeout(30):
            while True:
                worker.assert_running()
                queue = await client.workflow_service.describe_task_queue(
                    DescribeTaskQueueRequest(
                        namespace=settings.host.namespace,
                        task_queue=TaskQueue(name=settings.host.task_queue),
                        task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
                    )
                )
                if queue.pollers:
                    break
                await asyncio.sleep(0.05)
        yield worker
