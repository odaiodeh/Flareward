"""Owned live coding placement with trusted local publication and remote evaluation."""

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from pydantic import SecretStr
from runengine.invocation.config import ExecutorConfig, K8sRunnerConfig, OpenShellRunnerConfig

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import ApplicationDefinition, ProgramBody
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.models import CheckRequirement
from plugins.adlc.programs.coding import CodingFileWork
from plugins.adlc.programs.design import DesignProposal
from plugins.adlc.programs.designer import CodingDesignerConfig, CodingDesignWork
from plugins.adlc.programs.program import EngineeringCandidate
from plugins.artifacts.elements.specification import ELEMENT_SPECIFICATIONS as ARTIFACTS
from plugins.codex.config import CodexConfig
from plugins.codex.specification import CodexSpec
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS
from support.check_program_publication import CheckProgramSetup
from support.coding_resources import CodingResourceLibrary, saved_coding_candidate
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
        "LUMORA_CONFIGURATION_SECRETS": "false",
        "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "true",
        "LUMORA_PYTHON_CHECK_DIRECTORY": "/tmp/lumora-python-checks",
    }
    if isinstance(target, OpenShellRunnerConfig):
        policy = json.loads(
            files("lumora.bootstrap.settings")
            .joinpath("policies/openshell-restricted.json")
            .read_text()
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
    factory: str = "lumora.bootstrap.asgi:create_app",
    environment: Mapping[str, str] | None = None,
    review_timeout_seconds: int = 180,
) -> AsyncIterator[LiveFeature]:
    async with AsyncExitStack() as compute, AsyncExitStack() as services:
        coding = await compute.enter_async_context(
            backend.configured(
                {
                    "LUMORA_CONFIGURATION_SECRETS": "false",
                    "LUMORA_CODEX_API_KEY": key.get_secret_value(),
                },
                (NetworkEndpoint("api.openai.com", 443, ("/usr/local/bin/codex",)),),
            )
        )
        coding = coding.model_copy(
            update={
                "env": {
                    **(coding.env or {}),
                    "LUMORA_CODEX_SANDBOX_MODE": "danger-full-access",
                    "LUMORA_CODEX_API_KEY_FILE": coding.env["LUMORA_SECRETS_DIR"]
                    + "/LUMORA_CODEX_API_KEY",
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
                    "plugins.adlc.programs.design",
                    "plugins.adlc.programs.feature",
                    "plugins.adlc.programs.coding",
                    "plugins.adlc.programs.designer",
                    "plugins.testing.programs.python_check",
                ),
                element_modules=(
                    "plugins.codex.specification",
                    "plugins.testing.specification",
                ),
                library=True,
                factory=factory,
                verification_policies={"engineering@1": policy},
                check_programs={
                    "program@1": CheckProgramSetup(
                        python_verifier_definition(Identity.user("trusted-verifier"), "evaluation"),
                        policies(owner)[1].model_copy(update={"verifier": "program-ci"}),
                        input_artifact_max_bytes=65_536,
                    )
                },
                execution_profiles={
                    "coding": coding,
                    "evaluation": evaluation_target(backend.target),
                },
                environment={
                    **(environment or {}),
                    "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "false",
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
        design_coding = await CodingResourceLibrary(api.http, api.human).coding(
            CodexConfig(
                model="gpt-5.4-nano",
                timeout_seconds=60,
                max_commands=4,
                instructions=(
                    "Prepare a concise design proposal from the supplied task, files and criteria. "
                    "Do not implement or modify the feature. Do not inspect parent directories. "
                    "Return only the requested JSON proposal without Markdown fences."
                ),
            ),
            "coding",
            name="Feature designer",
        )
        designer = ProgramBody(
            implementation=ApplicationDefinition(
                implementation="coding_designer",
                version="1",
                config=CodingDesignerConfig(
                    coding=design_coding,
                    loader=configuration.loader,
                    execution=ExecutionSelection(profile="coding"),
                    artifact_execution=configuration.artifact_execution,
                ).model_dump(mode="json"),
            ),
            input_schema=CodingDesignWork.model_json_schema(),
            output_schema=DesignProposal.model_json_schema(),
        )
        programs = await publish_feature(
            api.http,
            api.human,
            owner,
            registry,
            body,
            "thread",
            runners=("program@1",),
            requirements=policy.requirements,
            review_timeout_seconds=review_timeout_seconds,
            max_check_polls=300,
            check_poll_interval_seconds=0.5,
            designer=designer,
        )
        yield LiveFeature(api, programs, key, compute, backend)
    await backend.assert_clean()
