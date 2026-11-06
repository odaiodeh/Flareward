"""Owned native Engineering API with a selected verifier and private test identities."""

import hashlib
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx
from fastapi import FastAPI
from inbound.http_api.app import create_app as http_app
from inbound.http_api.dependencies import HttpServices
from mas.application.artifacts.access_models import ArtifactActor
from mas.application.artifacts.service import ArtifactService
from mas.application.verification.check_ports import CheckRunnerPolicy
from mas.application.verification.check_service import CheckRunService, RegisteredCheckRunner
from mas.application.verification.models import VerificationPolicy
from mas.application.verification.program_checks import ProgramCheckConfiguration
from mas.application.verification.reports import CheckReportCollector
from mas.core.identity import Identity
from mas.domain.artifacts import BlobArtifactRef
from mas.domain.check_runs import CheckRun, CheckRunObservation, CheckRunStatus
from mas.domain.verification import CheckRequirement, CheckVerdict
from outbound.mongo.check_runs import MongoCheckRunRepository
from outbound.redis_client import owned_redis
from pymongo import AsyncMongoClient
from runengine.invocation.config import ExecutorConfig

from bootstrap.platform import compose_platform
from config.platform_settings import PlatformSettings
from support.check_program_publication import CheckProgramSetup
from support.identity import authenticated_cookie
from support.managed_access import managed_access_environment, managed_access_settings
from support.server import api_process


@dataclass(frozen=True)
class EngineeringAPI:
    http: httpx.AsyncClient
    human: dict[str, str] = field(repr=False)
    reviewer: dict[str, str] = field(repr=False)
    workspace: Path
    log: Path
    verifier: dict[str, str] | None = field(default=None, repr=False)
    check_binding: ProgramCheckConfiguration | None = field(default=None, repr=False)


@asynccontextmanager
async def engineering_api(
    owner: Identity,
    database: str,
    redis_uri: str,
    directory: Path,
    *,
    application_modules: tuple[str, ...] = (),
    element_modules: tuple[str, ...] = (),
    library: bool = False,
    factory: str = "support.engineering_api:create_app",
    environment: Mapping[str, str] | None = None,
    verification_policy: VerificationPolicy | None = None,
    check_program: CheckProgramSetup | None = None,
    execution_profiles: Mapping[str, ExecutorConfig] | None = None,
) -> AsyncIterator[EngineeringAPI]:
    settings = managed_access_settings(owner, database, redis_uri, directory)
    if execution_profiles is not None:
        settings = settings.model_copy(
            update={"execution_profiles": {**settings.execution_profiles, **execution_profiles}}
        )
    verification_policy = verification_policy or policies(owner)[0]
    settings = settings.model_copy(
        update={
            "verification_policies": {"engineering@1": verification_policy},
            "artifact_directory": directory / "artifacts",
            "artifact_workflow_enabled": True,
            "library": library,
            "configuration_secrets": library,
            "element_modules": (
                *settings.element_modules,
                "mas_plugins.artifacts.specification",
                "support.engineering_operations",
                *element_modules,
            ),
            "application_modules": (
                *settings.application_modules,
                "mas_plugins.engineering.program",
                "support.engineering_programs",
                *application_modules,
            ),
        }
    )
    workspace, log = directory / "workspaces", directory / "engineering-api.log"

    def receiver_environment(base: str) -> dict[str, str]:
        return {
            **managed_access_environment(base),
            "UNIFAI_ARTIFACT_ENDPOINT": base,
            "UNIFAI_ARTIFACT_ALLOW_INSECURE": "true",
            "UNIFAI_WORKSPACE_ROOT": str(workspace),
            **(environment or {}),
        }

    async with AsyncExitStack() as stack:
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = [
            await stack.enter_async_context(
                authenticated_cookie(redis, user, settings.secret_key.get_secret_value())
            )
            for user in (
                owner.id,
                "reviewer",
                *((check_program.definition.owner.id,) if check_program is not None else ()),
            )
        ]
        verifier = {"Cookie": "session=" + cookies[2]} if check_program is not None else None
        binding = None
        if check_program is not None:
            assert verifier is not None
            publication = settings.model_copy(
                update={
                    "verification_enabled": False,
                    "verification_policies": {},
                    "verification_authorities": {},
                }
            )
            async with api_process(
                publication,
                directory / "verifier-publication.log",
                environment=receiver_environment,
            ) as bootstrap:
                binding = await check_program.publish(bootstrap, verifier)
            settings = PlatformSettings.model_validate(
                {
                    **settings.model_dump(mode="python"),
                    "program_checks": {"program@1": binding},
                }
            )
        http = await stack.enter_async_context(
            api_process(
                settings,
                log,
                factory=factory,
                environment=receiver_environment,
            )
        )
        yield EngineeringAPI(
            http,
            {"Cookie": "session=" + cookies[0]},
            {"Cookie": "session=" + cookies[1]},
            workspace,
            log,
            verifier,
            binding,
        )


def policies(owner: Identity) -> tuple[VerificationPolicy, CheckRunnerPolicy]:
    return (
        VerificationPolicy(
            owners=(owner,),
            subject_kind="blob-artifact@1",
            requirements=(CheckRequirement(check="tests@1", verifiers=frozenset({"ci"})),),
            timeout_seconds=600,
        ),
        CheckRunnerPolicy(
            owners=(owner,),
            policies=frozenset({"engineering@1"}),
            check="tests@1",
            verifier="ci",
            subject_kind="blob-artifact@1",
        ),
    )


class DeterministicCheck:
    configuration_digest = "d" * 64

    def __init__(self, artifacts: ArtifactService) -> None:
        self._artifacts = artifacts

    def validate(self, run: CheckRun) -> None:
        BlobArtifactRef.model_validate(run.plan.subject.identity)

    async def submit(self, run: CheckRun) -> CheckRunObservation:
        reference = BlobArtifactRef.model_validate(run.plan.subject.identity)
        async with self._artifacts.open(reference, ArtifactActor(run.plan.owner)) as source:
            content = b"".join([chunk async for chunk in source])
        if (
            hashlib.sha256(content).hexdigest() != reference.sha256
            or len(content) != reference.size_bytes
        ):
            raise ValueError("Candidate bytes do not match the published identity")
        return CheckRunObservation(
            external_id="fixture:" + run.intent_id,
            status=CheckRunStatus.COMPLETED,
            verdict=CheckVerdict.PASSED
            if content == b"candidate verified\n"
            else CheckVerdict.FAILED,
        )

    async def reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        return None


def check_application(
    driver: Callable[[ArtifactService, CheckRunnerPolicy], RegisteredCheckRunner],
) -> FastAPI:
    settings = PlatformSettings()

    @asynccontextmanager
    async def services() -> AsyncIterator[HttpServices]:
        async with compose_platform(settings) as native:
            client = AsyncMongoClient(settings.mongo_uri.get_secret_value())
            try:
                assert native.verifications is not None
                assert native.artifacts is not None
                owner = settings.verification_policies["engineering@1"].owners[0]
                _, policy = policies(owner)
                checks = CheckRunService(
                    MongoCheckRunRepository(client[settings.mongo_database]),
                    native.verifications,
                    {"fixture@1": driver(native.artifacts, policy)},
                    reports=CheckReportCollector(native.artifacts),
                )
                yield replace(native, check_runs=checks)
            finally:
                await client.close()

    return http_app(services_factory=services)


def create_app() -> FastAPI:
    return check_application(
        lambda artifacts, policy: RegisteredCheckRunner(policy, DeterministicCheck(artifacts))
    )
