"""Integration composition owns the real local host and closes it after each test."""

import asyncio
import os
from dataclasses import dataclass

import pytest
from cryptography.fernet import Fernet
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.coordination.ports import RunHost
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.application import Application
from support.conditions import ELEMENT_SPECIFICATIONS as CONDITION_SPECIFICATIONS
from support.databases import isolated_mongo

from lumora.bootstrap.credentials import receiver_auth
from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from lumora.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from lumora.executions.adapters.run_engine.outbound.gateway import RunEngineGateway
from lumora.executions.service import ExecutionService
from lumora.programs.service import ProgramService
from lumora.services.auth.credentials.models import StoredCredential
from lumora.services.identity.domain import Identity
from lumora.services.sessions.adapters.memory.session_store import MemorySessionStore
from lumora.services.sessions.execution.program_sessions import ProgramSessionService


@dataclass(frozen=True)
class Platform:
    programs: ProgramService
    executions: ExecutionService
    owner: Identity
    compiler: ProgramCompiler
    host: RunHost
    records: MemoryExecutionRepository
    gateway: RunEngineGateway


@pytest.fixture
async def platform(application: Application):
    compiler = ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        {"thread": ThreadRunnerConfig(), "process": ProcessRunnerConfig(max_workers=1)},
        "thread",
    )
    async with RunHostBuilder.create(LocalHostConfig()) as host:
        records = MemoryExecutionRepository()
        gateway = RunEngineGateway(host, compiler)
        executions = ExecutionService(application.programs, records, gateway)
        yield Platform(
            application.programs, executions, application.owner, compiler, host, records, gateway
        )


@pytest.fixture
def condition_elements(application):
    for specification in CONDITION_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    return application.elements


@pytest.fixture
def session_store() -> MemorySessionStore:
    return MemorySessionStore()


@pytest.fixture
async def sessions(platform: Platform, session_store):
    return ProgramSessionService(session_store, platform.programs, platform.executions)


@pytest.fixture
async def mongo_database():
    uri = os.environ.get("LUMORA_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set LUMORA_TEST_MONGO_URI to run actual Mongo repository contracts")
    async with isolated_mongo(uri) as database:
        yield database


@pytest.fixture
async def transaction_database():
    uri = os.environ.get("LUMORA_TEST_MONGO_TRANSACTION_URI")
    if not uri:
        pytest.skip("Set LUMORA_TEST_MONGO_TRANSACTION_URI for atomic Mongo catalog tests")
    async with isolated_mongo(uri) as database:
        assert (await database.client.admin.command("hello")).get("setName"), (
            "The configured transaction service must support Mongo transactions"
        )
        yield database


@pytest.fixture
def redis_uri():
    value = os.environ.get("LUMORA_TEST_REDIS_URI")
    if not value:
        pytest.skip("Set LUMORA_TEST_REDIS_URI for actual Redis integration")
    return value


@pytest.fixture
def secret_settings(mongo_database, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("LUMORA_MONGO_URI", os.environ["LUMORA_TEST_MONGO_URI"])
    monkeypatch.setenv("LUMORA_MONGO_DATABASE", mongo_database.name)
    monkeypatch.setenv("LUMORA_CREDENTIAL_ENCRYPTION_KEY", key)
    monkeypatch.setenv("LUMORA_CONFIGURATION_SECRETS", "true")
    monkeypatch.setenv("LUMORA_INTERACTIONS", "disabled")
    return PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        interactions="disabled",
        authentication="development",
        development_user="owner",
        execution_profiles={
            "thread": ThreadRunnerConfig(),
            "process": ProcessRunnerConfig(max_workers=1),
        },
        default_execution_profile="thread",
    )


@pytest.fixture
async def inspection_settings(secret_settings):
    settings = secret_settings.model_copy(update={"library": True, "credentials": "mongo"})
    async with receiver_auth(settings) as auth:
        for user, token in (("human", "probe-server-private"), ("workspace", "wrong-private")):
            await asyncio.to_thread(
                auth.save_credential,
                StoredCredential(
                    user_id=user,
                    server_identifier="inspection",
                    scheme_type="api_key",
                    access_token=token,
                ),
            )
    return settings
