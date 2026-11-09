"""Owned native Engineering API with a selected verifier and private test identities."""

import hashlib
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

import httpx
from fastapi import FastAPI
from pymongo import AsyncMongoClient
from runengine.invocation.config import ExecutorConfig

from flareward.api.app import create_app as http_app
from flareward.api.dependencies import HttpServices
from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.services.artifacts.access_models import ArtifactActor
from flareward.services.artifacts.domain.models import BlobArtifactRef
from flareward.services.artifacts.service import ArtifactService
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from flareward.services.verification.adapters.mongo.check_runs import MongoCheckRunRepository
from flareward.services.verification.check_ports import CheckRunnerPolicy
from flareward.services.verification.check_service import CheckRunService, RegisteredCheckRunner
from flareward.services.verification.domain.check_runs import (
    CheckRun,
    CheckRunObservation,
    CheckRunStatus,
)
from flareward.services.verification.domain.models import CheckRequirement, CheckVerdict
from flareward.services.verification.models import VerificationPolicy
from flareward.services.verification.program_checks import ProgramCheckConfiguration
from flareward.services.verification.reports import CheckReportCollector
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
    verifiers: dict[str, dict[str, str]] = field(default_factory=dict, repr=False)
    check_bindings: dict[str, ProgramCheckConfiguration] = field(default_factory=dict)


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
    verification_policies: Mapping[str, VerificationPolicy] | None = None,
    check_programs: Mapping[str, CheckProgramSetup] | None = None,
    execution_profiles: Mapping[str, ExecutorConfig] | None = None,
) -> AsyncIterator[EngineeringAPI]:
    settings = managed_access_settings(owner, database, redis_uri, directory)
    if execution_profiles is not None:
        settings = settings.model_copy(
            update={"execution_profiles": {**settings.execution_profiles, **execution_profiles}}
        )
    verification_policies = (
        {"engineering@1": policies(owner)[0]}
        if verification_policies is None
        else dict(verification_policies)
    )
    check_programs = check_programs or {}
    settings = settings.model_copy(
        update={
            "verification_policies": verification_policies,
            "artifact_directory": directory / "artifacts",
            "artifact_workflow_enabled": True,
            "library": library,
            "configuration_secrets": library,
            "element_modules": (
                *settings.element_modules,
                "plugins.artifacts.elements.specification",
                "support.engineering_operations",
                *element_modules,
            ),
            "application_modules": (
                *settings.application_modules,
                "plugins.adlc.programs.program",
                "support.engineering_programs",
                *application_modules,
            ),
        }
    )
    workspace, log = directory / "workspaces", directory / "engineering-api.log"

    def receiver_environment(base: str) -> dict[str, str]:
        return {
            **managed_access_environment(base),
            "FLAREWARD_ARTIFACT_ENDPOINT": base,
            "FLAREWARD_ARTIFACT_ALLOW_INSECURE": "true",
            "FLAREWARD_WORKSPACE_ROOT": str(workspace),
            **(environment or {}),
        }

    async with AsyncExitStack() as stack:
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = {
            user: await stack.enter_async_context(
                authenticated_cookie(redis, user, settings.secret_key.get_secret_value())
            )
            for user in dict.fromkeys(
                (
                    owner.id,
                    "reviewer",
                    *(setup.definition.owner.id for setup in check_programs.values()),
                )
            )
        }
        verifiers = {
            name: {"Cookie": "session=" + cookies[setup.definition.owner.id]}
            for name, setup in check_programs.items()
        }
        bindings = {}
        if check_programs:
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
                for name, setup in check_programs.items():
                    bindings[name] = await setup.publish(bootstrap, verifiers[name])
            settings = PlatformSettings.model_validate(
                {
                    **settings.model_dump(mode="python"),
                    "program_checks": bindings,
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
            {"Cookie": "session=" + cookies[owner.id]},
            {"Cookie": "session=" + cookies["reviewer"]},
            workspace,
            log,
            verifiers,
            bindings,
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
