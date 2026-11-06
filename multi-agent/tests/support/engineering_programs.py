"""Deterministic candidate producer for Engineering integration tests."""

from mas.application.artifacts.operations import PublishedArtifact
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.programs.ports import ProgramRuntime
from mas.application.programs.registry import ApplicationRegistration
from mas.core.enums import ResourceCategory
from mas.domain.element_bundles import ElementBundle, ResourceDefinition, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.files import WorkspaceFile
from mas.domain.programs.models import ApplicationDefinition, ProgramBody
from mas.domain.verification import VerificationSubject
from mas_plugins.engineering.program import EngineeringCandidate, EngineeringConfig, EngineeringWork
from pydantic import BaseModel, ConfigDict, JsonValue

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
) -> EngineeringConfig:
    resolver, resources = ElementBundleResolver(registry), check_resources()
    return EngineeringConfig(
        verification_policy=verification_policy,
        runners=runners,
        request_verification=resolver.resolve(resources[1].key, resources),
        inspect_verification=resolver.resolve(resources[2].key, resources),
        start_check=resolver.resolve(resources[4].key, resources),
        refresh_check=resolver.resolve(resources[5].key, resources),
        review=review_definition(registry, profile, timeout_seconds=review_timeout_seconds).config,
        execution=ExecutionSelection(profile=profile),
        max_repairs=1,
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
