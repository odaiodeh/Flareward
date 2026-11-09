"""Opt-in real Temporal service, isolated queue, and application-owned runtime composition."""

import os
from dataclasses import dataclass
from uuid import uuid4

import pytest
from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from temporalio.client import Client

from flareward.bootstrap.settings.worker_settings import WorkerSettings
from flareward.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from flareward.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from flareward.executions.adapters.run_engine.outbound.gateway import RunEngineGateway
from flareward.executions.service import ExecutionService


@dataclass(frozen=True)
class DurableRuntime:
    executions: ExecutionService
    client: Client
    settings: WorkerSettings


@pytest.fixture
async def durable(application):
    endpoint = os.environ.get("FLAREWARD_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Set FLAREWARD_TEST_TEMPORAL_ENDPOINT for real durable worker contracts")
    config = TemporalHostConfig(
        endpoint=endpoint,
        task_queue="flareward-platform-test-" + uuid4().hex,
        invocation_heartbeat_timeout_seconds=0.5,
    )
    compiler = ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        {"thread": ThreadRunnerConfig(), "process": ProcessRunnerConfig(max_workers=1)},
        "thread",
    )
    client = await Client.connect(config.endpoint, namespace=config.namespace)
    async with RunHostBuilder.create(config) as host:
        yield DurableRuntime(
            ExecutionService(
                application.programs, MemoryExecutionRepository(), RunEngineGateway(host, compiler)
            ),
            client,
            WorkerSettings(
                host=config, application_modules=("support.programs",), interactions="disabled"
            ),
        )
