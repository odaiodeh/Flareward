"""Integration composition owns the real local host and closes it after each test."""

import asyncio
import os
from dataclasses import dataclass
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from mas.core.auth.credentials.models import StoredCredential
from mas.core.identity import Identity
from mas.execution.service import ExecutionService
from mas.programs.service import ProgramService
from mas.session.execution.program_sessions import ProgramSessionService
from outbound.memory.execution_repository import MemoryExecutionRepository
from outbound.memory.session_store import MemorySessionStore
from outbound.run_engine.compiler import ProgramCompiler
from outbound.run_engine.gateway import RunEngineGateway
from pymongo import AsyncMongoClient
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.coordination.ports import RunHost
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.application import Application
from support.conditions import ELEMENT_SPECIFICATIONS as CONDITION_SPECIFICATIONS

from bootstrap.credentials import receiver_auth
from config.platform_settings import PlatformSettings


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
    uri = os.environ.get("UNIFAI_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set UNIFAI_TEST_MONGO_URI to run actual Mongo repository contracts")
    client = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
    database = client[f"unifai_platform_test_{uuid4().hex}"]
    try:
        await client.admin.command("ping")
        yield database
    finally:
        await client.drop_database(database.name)
        await client.close()


@pytest.fixture
def redis_uri():
    value = os.environ.get("UNIFAI_TEST_REDIS_URI")
    if not value:
        pytest.skip("Set UNIFAI_TEST_REDIS_URI for actual Redis integration")
    return value


@pytest.fixture
def secret_settings(mongo_database, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("UNIFAI_MONGO_URI", os.environ["UNIFAI_TEST_MONGO_URI"])
    monkeypatch.setenv("UNIFAI_MONGO_DATABASE", mongo_database.name)
    monkeypatch.setenv("UNIFAI_CREDENTIAL_ENCRYPTION_KEY", key)
    monkeypatch.setenv("UNIFAI_CONFIGURATION_SECRETS", "true")
    monkeypatch.setenv("UNIFAI_INTERACTIONS", "disabled")
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
