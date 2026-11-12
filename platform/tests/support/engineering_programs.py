"""Deterministic candidate producer for Engineering integration tests."""

from pydantic import BaseModel, ConfigDict, JsonValue

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramBody
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle, ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.verification.domain.models import CheckRequirement, VerificationSubject
from lumora.services.workspaces.domain.files import WorkspaceFile
from plugins.adlc.programs.program import (
    EngineeringCandidate,
    EngineeringCompletion,
    EngineeringConfig,
    EngineeringWork,
)
from plugins.adlc.programs.reviewer import ReviewDependency
from plugins.artifacts.elements.operations import PublishedArtifact
from support.review_programs import confirmation_bundle
from support.verification_programs import check_resources


def engineering_configuration(
    registry: ElementRegistry,
    *,
    profile: str = "thread",
    verification_policy: str = "source@1",
    runners: tuple[str, ...] = ("ci@1",),
    max_polls: int = 2,
    poll_interval_seconds: float = 5,
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
                review=ReviewDependency(
                    policy="release@1",
                    confirmation=confirmation_bundle(registry),
                    execution=ExecutionSelection(profile=profile),
                ),
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
        implementation=CustomCoordinatorDefinition(
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


COORDINATORS = (
    CoordinatorRegistration(
        "engineering_candidate",
        "1",
        CandidateConfig,
        CustomCoordinatorStrategy(candidate),
        input_model=EngineeringWork,
        result_model=EngineeringCandidate,
    ),
    CoordinatorRegistration(
        "engineering_artifact_candidate",
        "1",
        ArtifactCandidateConfig,
        CustomCoordinatorStrategy(artifact_candidate),
        input_model=EngineeringWork,
        result_model=EngineeringCandidate,
    ),
)
