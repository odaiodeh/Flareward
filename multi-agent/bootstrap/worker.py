"""Own the generic Run Engine worker; coordination, recovery, and environments stay upstream."""

import asyncio
import logging
import signal
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from importlib import import_module

from mas.core.async_work import await_owned
from runengine.adapters.coordination.temporal.worker import CoordinationWorker
from runengine.adapters.invocation.environment_store import SqliteEnvironmentStore
from runengine.invocation.environment_records import EnvironmentStore
from temporalio.client import Client
from temporalio.worker import Worker

from bootstrap.programs import CORE_APPLICATION_MODULES
from config.worker_settings import WorkerSettings

logger = logging.getLogger(__name__)

# Installed coordination code and schemas are imported before replay. Application
# behavior still performs I/O through runtime invocation ports.
PLATFORM_MODULES = (
    "mas",
    "inbound.run_engine",
    "outbound.run_engine",
    "run_engine",
    "inbound.run_engine.programs",
    "inbound.run_engine.elements",
    "inbound.run_engine.schedules",
    "bootstrap.scheduling",
)


def workflow_modules(settings: WorkerSettings) -> tuple[str, ...]:
    modules = (
        *PLATFORM_MODULES,
        *CORE_APPLICATION_MODULES,
        *settings.application_modules,
        *settings.element_modules,
    )
    if settings.receiver_module:
        modules = (*modules, settings.receiver_module)
    return tuple(dict.fromkeys(modules))


@asynccontextmanager
async def compose_worker(settings: WorkerSettings) -> AsyncIterator[Worker]:
    modules = workflow_modules(settings)
    for name in modules:
        import_module(name)
    store: EnvironmentStore | None = None
    if settings.environment_sqlite is not None:
        store = await await_owned(
            asyncio.to_thread(SqliteEnvironmentStore, settings.environment_sqlite)
        )
    elif settings.environment_postgres is not None:
        factory = import_module(
            "runengine.adapters.invocation.postgres_environment_store"
        ).PostgresEnvironmentStore
        store = factory(settings.environment_postgres.get_secret_value())
    async with AsyncExitStack() as resources:
        owner = await resources.enter_async_context(
            CoordinationWorker(
                settings.host,
                application_modules=modules,
                environment_store=store,
                environment_reconciliation_interval=settings.environment_reconciliation_interval,
            )
        )
        client = await Client.connect(settings.host.endpoint, namespace=settings.host.namespace)
        worker = await resources.enter_async_context(owner.create_worker(client))
        yield worker


async def run_worker(settings: WorkerSettings) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGTERM, signal.SIGINT)
    for selected in signals:
        loop.add_signal_handler(selected, stop.set)
    try:
        async with compose_worker(settings):
            logger.info("UnifAI program worker started on queue %s", settings.host.task_queue)
            await stop.wait()
    finally:
        for selected in signals:
            loop.remove_signal_handler(selected)
