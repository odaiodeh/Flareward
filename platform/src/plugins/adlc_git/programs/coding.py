"""Coding agents publish Git work; an admitted resolver independently checks it."""

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError, model_validator

from lumora.elements.coding.contracts import CodingInput, CodingOutcome
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.files import ProgramFileInputs
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.resources.domain.bundles import ElementBundle
from lumora.services.verification.domain.models import VerificationSubject
from lumora.services.workspaces.domain.files import ArtifactFile, InputFile
from plugins.adlc.programs.contracts import require_service_operation, validate_result
from plugins.adlc.programs.program import (
    EngineeringCandidate,
    EngineeringWork,
)
from plugins.git.domain.repositories import GitRevision, RepositoryId
from plugins.git.operations import ResolveGitRevision


class CodingGitWork(EngineeringWork[CodingInput]):
    """Installed typed identity for Git-producing coding work."""


class CodingGitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    coding: ElementBundle
    loader: ElementBundle
    resolver: ElementBundle
    repository: RepositoryId
    execution: ExecutionSelection
    artifact_execution: ExecutionSelection
    repository_execution: ExecutionSelection

    @model_validator(mode="after")
    def admitted_resolver(self) -> CodingGitConfig:
        require_service_operation(self.resolver, "resolve_git_revision", "git_repository")
        return self


class CodingGitCandidate:
    def __init__(self, runtime: ProgramRuntime, config: CodingGitConfig) -> None:
        self._runtime, self._config = runtime, config

    def _inputs(self, work: CodingGitWork) -> tuple[InputFile, ...]:
        files = {file.path: file for file in work.task.files}
        feedback = work.feedback
        if feedback is not None:
            previous = validate_result(GitRevision, feedback.candidate.identity)
            if (
                feedback.candidate.kind != "git-revision@1"
                or previous.repository != self._config.repository
            ):
                raise ValueError("Git repair requires a candidate from the configured repository")
            for evidence in feedback.evidence:
                for report in evidence.reports:
                    source = ArtifactFile(
                        artifact=report.content,
                        path=".lumora/reports/" + report.content.artifact_id,
                    )
                    if source.path in files and files[source.path] != source:
                        raise ValueError("Repair reports conflict with configured workspace inputs")
                    files[source.path] = source
        return tuple(files.values())

    async def run(self, work: CodingGitWork) -> EngineeringCandidate:
        config = self._config
        files = await ProgramFileInputs(
            self._runtime, config.loader, config.artifact_execution
        ).prepare(self._inputs(work))
        context = [
            work.task.context,
            "Commit the requested work and publish it to the configured retained repository "
            + config.repository
            + ". Use your available repository tools. "
            "Return only JSON with repository and the full immutable commit ID as commit. "
            "An unpublished local commit is not a completed candidate.",
        ]
        if work.feedback is not None:
            context.append("Previous attempt feedback:\n" + work.feedback.model_dump_json())
        request = CodingInput(
            prompt=work.task.prompt, context="\n\n".join(filter(None, context)), files=files
        )
        coded = validate_result(
            CodingOutcome,
            await self._runtime.invoke_element(
                config.coding,
                request.model_dump(mode="json"),
                key="code",
                execution=config.execution,
            ),
        )
        try:
            reported = GitRevision.model_validate_json(coded.content)
        except ValidationError:
            raise ValueError("Coding agent did not return an immutable Git revision") from None
        if reported.repository != config.repository:
            raise ValueError("Coding agent reported a different repository")
        observed = validate_result(
            GitRevision,
            await self._runtime.invoke_element(
                config.resolver,
                ResolveGitRevision(reference=reported.commit).model_dump(mode="json"),
                key="resolve-published",
                execution=config.repository_execution,
            ),
        )
        if observed != reported:
            raise ValueError("Published repository does not contain the reported candidate")
        return EngineeringCandidate(
            subject=VerificationSubject(
                kind="git-revision@1", identity=observed.model_dump(mode="json")
            )
        )


async def coding_git_candidate(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, CodingGitConfig)
    return (
        await CodingGitCandidate(runtime, config).run(validate_result(CodingGitWork, inputs))
    ).model_dump(mode="json")


COORDINATORS = (
    CoordinatorRegistration(
        "coding_git_candidate",
        "1",
        CodingGitConfig,
        CustomCoordinatorStrategy(coding_git_candidate),
        name="Git coding candidate",
        description="Code and publish through the agent, then resolve the exact admitted revision",
        input_model=CodingGitWork,
        result_model=EngineeringCandidate,
    ),
)
