"""Native production composition with a durable GitHub protocol fixture as its external peer."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from inbound.http_api.app import create_app as http_app
from inbound.http_api.dependencies import HttpServices
from mas.application.verification.check_service import CheckRunService, RegisteredCheckRunner
from mas.application.verification.reports import CheckReportCollector
from mas.core.identity import Identity
from mas_plugins.ci.github import GitHubActionsCheckRunner
from mas_plugins.ci.github_reports import GitHubCheckReports
from outbound.mongo.check_runs import MongoCheckRunRepository
from pydantic import SecretStr
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from runengine.adapters.coordination.config import LocalHostConfig

from bootstrap.platform import compose_platform
from config.platform_settings import PlatformSettings
from support.check_runs import source_policy
from support.github_checks import GitHubProtocol, github_configuration


def check_api_settings(
    owner: Identity,
    database: str,
    redis_uri: str,
    *,
    development: bool = False,
    artifact_directory: Path | None = None,
) -> PlatformSettings:
    return PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        authentication="development" if development else "session",
        development_user=owner.id if development else "",
        secret_key=SecretStr("ci-cookie-fixture"),
        mongo_uri=SecretStr(os.environ["UNIFAI_TEST_MONGO_URI"]),
        mongo_database=database,
        redis_uri=SecretStr(redis_uri),
        verification_enabled=True,
        verification_policies={
            "source@1": source_policy(owner, requires_reports=artifact_directory is not None)
        },
        github_checks={
            "github@1": github_configuration(owner, reports=artifact_directory is not None)
        },
        artifact_directory=artifact_directory,
    )


class DurableGitHubProtocol:
    """Persists a wire stand-in across API restarts; it does not run GitHub jobs."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.fixture_github_runs
        self._artifacts = database.fixture_github_artifacts

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        wire = GitHubProtocol(lose_acknowledgement=True, reports=True)
        if request.method == "POST":
            try:
                return wire(request)
            finally:
                for run in wire.runs:
                    await self._collection.insert_one({"_id": run["id"], "run": run})
                for artifact in wire.artifacts:
                    await self._artifacts.insert_one({"_id": artifact["id"], "artifact": artifact})
        wire.runs = [item["run"] async for item in self._collection.find()]
        wire.artifacts = [item["artifact"] async for item in self._artifacts.find()]
        return wire(request)


def create_app() -> FastAPI:
    settings = PlatformSettings()

    @asynccontextmanager
    async def services() -> AsyncIterator[HttpServices]:
        async with compose_platform(settings) as native:
            client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
                settings.mongo_uri.get_secret_value()
            )
            try:
                database = client[settings.mongo_database]
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(DurableGitHubProtocol(database))
                ) as http:
                    assert native.verifications is not None
                    checks = CheckRunService(
                        MongoCheckRunRepository(database),
                        native.verifications,
                        {
                            name: RegisteredCheckRunner(
                                binding.policy,
                                GitHubActionsCheckRunner(binding, http),
                                GitHubCheckReports(binding, http) if binding.report_names else None,
                            )
                            for name, binding in settings.github_checks.items()
                        },
                        reports=CheckReportCollector(native.artifacts)
                        if native.artifacts is not None
                        else None,
                    )
                    yield replace(native, check_runs=checks)
            finally:
                await client.close()

    return http_app(services_factory=services)
