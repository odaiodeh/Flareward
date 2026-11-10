"""Deployment selection and infrastructure composition stay outside scenarios."""

import os
import time
from contextlib import AsyncExitStack
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.invocation.config import ThreadRunnerConfig
from support.calendar import CalendarDeployment
from support.deployment_backend import NetworkEndpoint
from support.identity import session_cookie
from support.server import api_process
from support.telemetry import trace_collector
from support.temporal import replay, worker_process
from temporalio.client import Client

from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.identity.domain import Identity


def pytest_addoption(parser):
    parser.addoption(
        "--platform-backends", default="", help="Explicit k8s,openshell deployment matrix"
    )
    parser.addoption("--platform-hosts", default="local,temporal")


def pytest_generate_tests(metafunc):
    if "remote_backend" in metafunc.fixturenames:
        selected = metafunc.config.getoption("--platform-backends")
        names = selected.split(",") if selected else [""]
        if selected and (not set(names) <= {"k8s", "openshell"} or len(names) != len(set(names))):
            raise pytest.UsageError("Select distinct k8s,openshell platform backends")
        if selected:
            required = ["LUMORA_TEST_MONGO_URI", "LUMORA_TEST_REDIS_URI"]
            if "temporal" in metafunc.config.getoption("--platform-hosts").split(","):
                required.append("LUMORA_TEST_TEMPORAL_ENDPOINT")
            missing = [name for name in required if not os.environ.get(name)]
            if missing:
                raise pytest.UsageError(
                    "Remote deployment selection requires " + ", ".join(missing)
                )
        metafunc.parametrize("remote_backend", names, indirect=True)
    if "deployment_host" in metafunc.fixturenames:
        names = metafunc.config.getoption("--platform-hosts").split(",")
        if not set(names) <= {"local", "temporal"} or len(names) != len(set(names)):
            raise pytest.UsageError("Select distinct local,temporal platform hosts")
        metafunc.parametrize("deployment_host", names)


@pytest.fixture
async def remote_backend(request):
    if not request.param:
        pytest.skip("Select --platform-backends for actual remote deployment scenarios")
    module = import_module(
        "support."
        + {"k8s": "kubernetes_deployment", "openshell": "openshell_deployment"}[request.param]
    )
    async with module.backend() as backend:
        yield backend


@pytest.fixture
async def deployed_remote(remote_backend, deployment_host, mongo_database, tmp_path):
    redis_uri = os.environ["LUMORA_TEST_REDIS_URI"]
    host = (
        LocalHostConfig()
        if deployment_host == "local"
        else TemporalHostConfig(
            endpoint=os.environ["LUMORA_TEST_TEMPORAL_ENDPOINT"],
            task_queue="lumora-remote-" + uuid4().hex,
            invocation_timeout_seconds=180,
        )
    )
    secret, identity_id = uuid4().hex, uuid4().hex
    settings = PlatformSettings(
        host=host,
        mongo_uri=SecretStr(os.environ["LUMORA_TEST_MONGO_URI"]),
        mongo_database=mongo_database.name,
        storage="mongo",
        authentication="session",
        secret_key=SecretStr(secret),
        redis_uri=SecretStr(redis_uri),
        interactions="disabled",
        element_modules=("support.remote",),
        application_modules=("support.programs",),
        execution_profiles={"thread": ThreadRunnerConfig(), "remote": remote_backend.target},
        default_execution_profile="thread",
        reconcile_interval=0.05,
    )
    async with owned_redis(redis_uri, decode_responses=True) as redis:
        identity_key = "identity:session:" + identity_id
        await redis.hset(
            identity_key,
            mapping={
                "username": "alice",
                "access_token": "fixture-token",
                "session_expires_at": time.time() + 600,
            },
        )
        await redis.expire(identity_key, 600)
        try:
            async with AsyncExitStack() as owned:
                replay_history = None
                if deployment_host == "temporal":
                    worker = WorkerSettings.model_validate(
                        {
                            **settings.model_dump(mode="python"),
                            "environment_sqlite": tmp_path / "environments.sqlite",
                        }
                    )
                    await owned.enter_async_context(worker_process(worker, tmp_path / "worker.log"))
                    native = await Client.connect(host.endpoint)

                    async def replay_history(run_id):
                        await replay(native, worker, run_id)

                http = await owned.enter_async_context(api_process(settings, tmp_path / "api.log"))
                http.cookies.set("session", session_cookie(identity_id, secret))
                yield SimpleNamespace(
                    http=http,
                    owner=Identity.user("alice"),
                    backend=remote_backend,
                    settings=settings,
                    replay=replay_history,
                )
        finally:
            await redis.delete(identity_key)


@pytest.fixture
async def calendar_deployment(secret_settings, tmp_path):
    endpoint = os.environ.get("LUMORA_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Set the Temporal endpoint for native calendar deployment contracts")
    settings = secret_settings.model_copy(
        update={
            "host": TemporalHostConfig(
                endpoint=endpoint, task_queue="lumora-calendar-" + uuid4().hex
            ),
            "application_modules": ("support.programs",),
            "element_modules": ("support.elements",),
            "reconcile_interval": 0.05,
        }
    )
    worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
    native = await Client.connect(endpoint, namespace=settings.host.namespace)
    deployment = CalendarDeployment(settings, worker, native)
    async with worker_process(worker, tmp_path / "worker.log"):
        try:
            yield deployment
        finally:
            await deployment.close_schedules()


@pytest.fixture
async def configured_remote(remote_backend, deployment_host, mongo_database, tmp_path):
    host = (
        LocalHostConfig()
        if deployment_host == "local"
        else TemporalHostConfig(
            endpoint=os.environ["LUMORA_TEST_TEMPORAL_ENDPOINT"],
            task_queue="lumora-secrets-" + uuid4().hex,
        )
    )
    public_key, secret_key = "public-" + uuid4().hex, "private-" + uuid4().hex
    async with trace_collector() as collector, AsyncExitStack() as owned:
        values = {
            "LUMORA_TRACING": "langfuse",
            "LUMORA_LANGFUSE_PUBLIC_KEY": public_key,
            "LUMORA_LANGFUSE_SECRET_KEY": secret_key,
            "LUMORA_LANGFUSE_BASE_URL": collector.base_url.replace(
                "127.0.0.1", "host.docker.internal"
            ),
            "LUMORA_TRACING_TIMEOUT": "5",
        }
        target = await owned.enter_async_context(
            remote_backend.configured(
                values, (NetworkEndpoint("host.docker.internal", collector.port),)
            )
        )
        settings = PlatformSettings(
            host=host,
            storage="mongo",
            mongo_uri=SecretStr(os.environ["LUMORA_TEST_MONGO_URI"]),
            mongo_database=mongo_database.name,
            interactions="disabled",
            authentication="development",
            development_user="owner",
            receiver_module="lumora.bootstrap.receiver",
            element_modules=("support.tracing_elements",),
            execution_profiles={"remote": target},
            default_execution_profile="remote",
        )
        native = None
        if deployment_host == "temporal":
            worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
            await owned.enter_async_context(worker_process(worker, tmp_path / "worker.log"))
            native = await Client.connect(host.endpoint)
        else:
            worker = None
        http = await owned.enter_async_context(api_process(settings, tmp_path / "api.log"))
        yield SimpleNamespace(
            http=http,
            collector=collector,
            secret=secret_key,
            public=public_key,
            native=native,
            worker=worker,
            target=target,
            database=mongo_database,
        )
