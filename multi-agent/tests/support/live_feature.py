"""Owned live coding placement with trusted local publication and remote evaluation."""

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import ApplicationDefinition, ProgramBody
from mas.domain.verification import CheckRequirement
from mas_plugins.artifacts.specification import ELEMENT_SPECIFICATIONS as ARTIFACTS
from mas_plugins.coding.codex.config import CodexConfig
from mas_plugins.coding.codex.specification import CodexSpec
from mas_plugins.engineering.coding import CodingFileWork
from mas_plugins.engineering.program import EngineeringCandidate
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from mas_plugins.verification.specification import ELEMENT_SPECIFICATIONS as CHECKS
from pydantic import SecretStr
from runengine.invocation.config import ExecutorConfig, K8sRunnerConfig, OpenShellRunnerConfig

from support.check_program_publication import CheckProgramSetup
from support.coding_resources import saved_coding_candidate
from support.deployment_backend import DeploymentBackend, NetworkEndpoint
from support.engineering_api import EngineeringAPI, engineering_api, policies
from support.feature_api import FeaturePrograms, publish_feature
from support.python_checks import python_verifier_definition


@dataclass(frozen=True)
class LiveFeature:
    api: EngineeringAPI
    programs: FeaturePrograms
    key: SecretStr = field(repr=False)
    _compute: AsyncExitStack = field(repr=False)
    _backend: DeploymentBackend = field(repr=False)

    async def release_compute(self) -> None:
        """Collect only fixture-owned compute while keeping artifact HTTP available."""
        await self._compute.aclose()
        await self._backend.assert_clean()


def evaluation_target(target: ExecutorConfig) -> ExecutorConfig:
    if not isinstance(target, (K8sRunnerConfig, OpenShellRunnerConfig)):
        raise ValueError("Live evaluation requires an isolated deployment profile")
    data = target.model_dump(mode="python")
    data["env"] = {
        **(target.env or {}),
        "UNIFAI_CONFIGURATION_SECRETS": "false",
        "UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED": "true",
        "UNIFAI_PYTHON_CHECK_DIRECTORY": "/tmp/unifai-python-checks",
    }
    if isinstance(target, OpenShellRunnerConfig):
        policy = json.loads(
            files("config").joinpath("policies/openshell-restricted.json").read_text()
        )
        policy["network_policies"] = {}
        data["policy"] = policy
    return type(target).model_validate(data)


@asynccontextmanager
async def live_feature(
    backend: DeploymentBackend,
    key: SecretStr,
    owner: Identity,
    database: str,
    redis_uri: str,
    directory: Path,
    *,
    factory: str = "bootstrap.asgi:create_app",
    environment: Mapping[str, str] | None = None,
    review_timeout_seconds: int = 180,
) -> AsyncIterator[LiveFeature]:
    async with AsyncExitStack() as compute, AsyncExitStack() as services:
        coding = await compute.enter_async_context(
            backend.configured(
                {
                    "UNIFAI_CONFIGURATION_SECRETS": "false",
                    "UNIFAI_CODEX_API_KEY": key.get_secret_value(),
                },
                (NetworkEndpoint("api.openai.com", 443, ("/usr/local/bin/codex",)),),
            )
        )
        coding = coding.model_copy(
            update={
                "env": {
                    **(coding.env or {}),
                    "UNIFAI_CODEX_SANDBOX_MODE": "danger-full-access",
                    "UNIFAI_CODEX_API_KEY_FILE": coding.env["UNIFAI_SECRETS_DIR"]
                    + "/UNIFAI_CODEX_API_KEY",
                }
            }
        )
        registry = ElementRegistry()
        for specification in (*ARTIFACTS, *REVIEWS, *CHECKS, CodexSpec):
            registry.register_spec_class(specification)
        policy = policies(owner)[0].model_copy(
            update={
                "requirements": (
                    CheckRequirement(
                        check="tests@1", verifiers=frozenset({"program-ci"}), requires_reports=True
                    ),
                )
            }
        )
        api = await services.enter_async_context(
            engineering_api(
                owner,
                database,
                redis_uri,
                directory,
                application_modules=(
                    "mas_plugins.engineering.design",
                    "mas_plugins.engineering.feature",
                    "mas_plugins.engineering.coding",
                    "support.feature_design",
                    "mas_plugins.testing.program",
                ),
                element_modules=(
                    "mas_plugins.coding.codex.specification",
                    "mas_plugins.testing.specification",
                ),
                library=True,
                factory=factory,
                verification_policy=policy,
                check_program=CheckProgramSetup(
                    python_verifier_definition(Identity.user("trusted-verifier"), "evaluation"),
                    policies(owner)[1].model_copy(update={"verifier": "program-ci"}),
                    input_artifact_max_bytes=65_536,
                ),
                execution_profiles={
                    "coding": coding,
                    "evaluation": evaluation_target(backend.target),
                },
                environment={
                    **(environment or {}),
                    "UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED": "false",
                },
            )
        )
        configuration = await saved_coding_candidate(
            api.http,
            api.human,
            profile="coding",
            artifact_profile="thread",
            config=CodexConfig(
                model="gpt-5.4-nano",
                timeout_seconds=60,
                max_commands=4,
                instructions=(
                    "Implement the small requested deliverable in the current workspace. "
                    "Use only this workspace and the supplied files. Do not inspect parent or "
                    "other directories. Keep commands and the final response brief."
                ),
            ),
        )
        retained = backend.name == "k8s"
        if retained:
            configuration = configuration.model_copy(
                update={"execution": ExecutionSelection(environment="coding")}
            )
        body = ProgramBody(
            implementation=ApplicationDefinition(
                implementation="coding_file_candidate",
                version="1",
                config=configuration.model_dump(mode="json"),
                environments={"coding": "coding"} if retained else {},
            ),
            input_schema=CodingFileWork.model_json_schema(),
            output_schema=EngineeringCandidate.model_json_schema(),
        )
        programs = await publish_feature(
            api.http,
            api.human,
            owner,
            registry,
            body,
            "thread",
            runners=("program@1",),
            review_timeout_seconds=review_timeout_seconds,
            max_check_polls=300,
            check_poll_interval_seconds=0.5,
        )
        yield LiveFeature(api, programs, key, compute, backend)
    await backend.assert_clean()
