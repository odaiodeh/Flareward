"""Deterministic candidate producer for Engineering integration tests."""

from pydantic import BaseModel, ConfigDict, JsonValue

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import ApplicationDefinition, ProgramBody
from flareward.programs.ports import ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import ElementBundle, ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.verification.domain.models import CheckRequirement, VerificationSubject
from flareward.services.workspaces.domain.files import WorkspaceFile
from plugins.adlc.programs.program import (
    EngineeringCandidate,
    EngineeringCompletion,
    EngineeringConfig,
    EngineeringWork,
)
from plugins.artifacts.elements.operations import PublishedArtifact
from support.review_programs import review_definition
from support.verification_programs import check_resources


def engineering_configuration(
    registry: ElementRegistry,
    *,
    profile: str = "thread",
    verification_policy: str = "source@1",
    runners: tuple[str, ...] = ("ci@1",),
    max_polls: int = 2,
    poll_interval_seconds: float = 5,
    review_timeout_seconds: int = 60,
    requirements: tuple[CheckRequirement, ...] | None = None,
) -> EngineeringConfig:
    resolver, resources = ElementBundleResolver(registry), check_resources()
    return EngineeringConfig(
        default_completion="default",
        completions=(
            EngineeringCompletion(
                name="default",
                candidate_schema=EngineeringCandidate.model_json_schema(),
                verification_policy=verification_policy,
                requirements=requirements
                if requirements is not None
                else (CheckRequirement(check="tests@1", verifiers=frozenset({"github-ci"})),),
                runners=runners,
                review=review_definition(
                    registry, profile, timeout_seconds=review_timeout_seconds
                ).config,
                max_repairs=1,
            ),
        ),
        request_verification=resolver.resolve(resources[1].key, resources),
        inspect_verification=resolver.resolve(resources[2].key, resources),
        start_check=resolver.resolve(resources[4].key, resources),
        refresh_check=resolver.resolve(resources[5].key, resources),
        execution=ExecutionSelection(profile=profile),
        max_polls=max_polls,
        poll_interval_seconds=poll_interval_seconds,
    )


def artifact_candidate_body(
    registry: ElementRegistry, profile: str, *, workspace: str | None = None
) -> ProgramBody:
    resources = (
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.PROVIDER, rid="artifact-store"),
            type_key="artifact_store",
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="publisher"),
            type_key="publish_artifact",
            config={"store": "$ref:artifact-store", "namespace": "engineering"},
        ),
    )
    return ProgramBody(
        implementation=ApplicationDefinition(
            implementation="engineering_artifact_candidate",
            version="1",
            config=ArtifactCandidateConfig(
                publisher=ElementBundleResolver(registry).resolve(resources[1].key, resources),
                execution=ExecutionSelection(profile=profile),
                workspace=workspace,
            ).model_dump(mode="json"),
        ),
        input_schema=EngineeringWork.model_json_schema(),
        output_schema=EngineeringCandidate.model_json_schema(),
    )


class CandidateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactCandidateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publisher: ElementBundle
    execution: ExecutionSelection
    workspace: str | None = None


async def candidate(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    work = EngineeringWork.model_validate(inputs)
    return EngineeringCandidate(
        subject=VerificationSubject(
            kind="document@1", identity={"sha256": ("a" if work.attempt == 0 else "b") * 64}
        )
    ).model_dump(mode="json")


async def artifact_candidate(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, ArtifactCandidateConfig)
    work = EngineeringWork.model_validate(inputs)
    workspace = config.workspace
    if workspace is None and isinstance(work.task, dict):
        workspace = work.task.get("workspace")
    if not isinstance(workspace, str):
        raise ValueError("Fixture task requires its root workspace")
    file = WorkspaceFile(
        workspace=workspace, path="first.txt" if work.attempt == 0 else "repair.txt"
    )
    published = PublishedArtifact.model_validate(
        await runtime.invoke_element(
            config.publisher,
            file.model_dump(mode="json"),
            key="publish",
            execution=config.execution,
        )
    )
    return EngineeringCandidate(
        subject=VerificationSubject(
            kind="blob-artifact@1", identity=published.artifact.model_dump(mode="json")
        )
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "engineering_candidate",
        "1",
        CandidateConfig,
        candidate,
        input_model=EngineeringWork,
        result_model=EngineeringCandidate,
    ),
    ApplicationRegistration(
        "engineering_artifact_candidate",
        "1",
        ArtifactCandidateConfig,
        artifact_candidate,
        input_model=EngineeringWork,
        result_model=EngineeringCandidate,
    ),
)
