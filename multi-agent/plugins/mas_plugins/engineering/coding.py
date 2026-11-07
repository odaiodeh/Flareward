"""Compose prepared coding inputs and durable single-file Engineering candidates."""

from pathlib import PurePosixPath

from mas.application.artifacts.operations import PublishedArtifact
from mas.application.artifacts.program_inputs import ProgramFileInputs
from mas.application.coding.contracts import CodingInput, CodingOutcome
from mas.application.programs.ports import ProgramRuntime
from mas.application.programs.registry import ApplicationRegistration
from mas.domain.artifacts import BlobArtifactRef
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.files import ArtifactFile, InlineFile, InputFile, WorkspaceFile
from mas.domain.verification import VerificationSubject
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from .program import EngineeringCandidate, EngineeringWork, validate_result


class CodingFileWork(EngineeringWork[CodingInput]):
    """Installed model identity for portable invocation, with typed coding input."""


class CodingFileCandidateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    coding: ElementBundle
    loader: ElementBundle
    reader: ElementBundle
    publisher: ElementBundle
    path: str = Field(min_length=1, max_length=4096)
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    artifact_execution: ExecutionSelection

    @field_validator("path")
    @classmethod
    def contained_path(cls, value: str) -> str:
        return WorkspaceFile(workspace="validation", path=value).path


class CodingFileCandidate:
    """Return published bytes, never a candidate inferred from an agent's prose."""

    def __init__(self, runtime: ProgramRuntime, config: CodingFileCandidateConfig) -> None:
        self._runtime, self._config = runtime, config
        self._files = ProgramFileInputs(runtime, config.loader, config.artifact_execution)

    def _inputs(self, work: EngineeringWork[CodingInput]) -> tuple[InputFile, ...]:
        files = {str(PurePosixPath(file.path)): file for file in work.task.files}
        feedback = work.feedback
        if feedback is not None:
            if feedback.candidate.kind != "blob-artifact@1":
                raise ValueError("File repair requires an immutable blob candidate")
            artifact = validate_result(BlobArtifactRef, feedback.candidate.identity)
            files[str(PurePosixPath(self._config.path))] = ArtifactFile(
                artifact=artifact, path=self._config.path
            )
            for evidence in feedback.evidence:
                for report in evidence.reports:
                    source = ArtifactFile(
                        artifact=report.content,
                        path=".unifai/reports/" + report.content.artifact_id,
                    )
                    previous = files.get(source.path)
                    if previous is not None and previous != source:
                        raise ValueError("Repair reports conflict with configured workspace inputs")
                    files[source.path] = source
        return tuple(files.values())

    async def run(self, work: EngineeringWork[CodingInput]) -> EngineeringCandidate:
        request = work.task
        files = await self._files.prepare(self._inputs(work))
        context = [request.context, f"Write the deliverable to workspace path: {self._config.path}"]
        if work.feedback is not None:
            context.append("Previous attempt feedback:\n" + work.feedback.model_dump_json())
        request = validate_result(
            CodingInput,
            {
                "prompt": request.prompt,
                "context": "\n\n".join(filter(None, context)),
                "files": [file.model_dump(mode="json") for file in files],
            },
        )
        coded = validate_result(
            CodingOutcome,
            await self._runtime.invoke_element(
                self._config.coding,
                request.model_dump(mode="json"),
                key="code",
                execution=self._config.execution,
            ),
        )
        source = WorkspaceFile(workspace=coded.workspace, path=self._config.path)
        exported = validate_result(
            InlineFile,
            await self._runtime.invoke_element(
                self._config.reader,
                source.model_dump(mode="json"),
                key="read",
                execution=self._config.execution,
            ),
        )
        if exported.path != self._config.path:
            raise ValueError("Exported file does not match the requested candidate path")
        published = validate_result(
            PublishedArtifact,
            await self._runtime.invoke_element(
                self._config.publisher,
                exported.model_dump(mode="json"),
                key="publish",
                execution=self._config.artifact_execution,
            ),
        )
        if (
            published.artifact.sha256 != exported.content.identity.sha256
            or published.artifact.size_bytes != exported.content.identity.size_bytes
        ):
            raise ValueError("Published candidate does not match the exported content")
        return EngineeringCandidate(
            subject=VerificationSubject(
                kind="blob-artifact@1", identity=published.artifact.model_dump(mode="json")
            )
        )


async def coding_file_candidate(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, CodingFileCandidateConfig)
    return (
        await CodingFileCandidate(runtime, config).run(validate_result(CodingFileWork, inputs))
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "coding_file_candidate",
        "1",
        CodingFileCandidateConfig,
        coding_file_candidate,
        input_model=CodingFileWork,
        result_model=EngineeringCandidate,
    ),
)
