"""Inspect an admitted Git file before isolated evaluation and trusted comparison."""

from pydantic import BaseModel, JsonValue, field_validator

from flareward.executions.domain.preferences import ExecutionSelection
from flareward.models import Model
from flareward.programs.ports import ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import ElementBundle
from flareward.services.verification.domain.models import VerificationSubject
from flareward.services.verification.program_checks import CheckProgramInput, CheckProgramResult
from plugins.git.domain.repositories import GitFile, GitFileContent, GitRevision
from plugins.testing.programs.python_check import (
    PythonFunctionCheck,
    PythonFunctionCheckConfig,
)


class GitPythonCheckConfig(Model):
    reader: ElementBundle
    path: str
    source_execution: ExecutionSelection
    comparison: PythonFunctionCheckConfig

    @field_validator("path")
    @classmethod
    def contained_path(cls, value: str) -> str:
        return GitFile.contained_path(value)


class GitPythonCheck:
    def __init__(self, runtime: ProgramRuntime, config: GitPythonCheckConfig) -> None:
        self._runtime, self._config = runtime, config

    async def run(self, request: CheckProgramInput) -> CheckProgramResult:
        revision = GitRevision.model_validate(request.subject.identity)
        if (
            request.artifact is not None
            or request.subject.fingerprint
            != VerificationSubject(
                kind="git-revision@1", identity=revision.model_dump(mode="json")
            ).fingerprint
        ):
            raise ValueError("Git checks require an exact admitted revision")
        file = GitFile(revision=revision, path=self._config.path)
        content = GitFileContent.model_validate(
            await self._runtime.invoke_element(
                self._config.reader,
                file.model_dump(mode="json"),
                key="read-source",
                execution=self._config.source_execution,
            )
        )
        if content.revision != revision or content.path != file.path:
            raise ValueError("Git file reader identifies different source")
        return await PythonFunctionCheck(self._runtime, self._config.comparison).evaluate(
            request, content.content
        )


async def git_python_check(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, GitPythonCheckConfig)
    return (
        await GitPythonCheck(runtime, config).run(CheckProgramInput.model_validate(inputs))
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "git_python_function_check",
        "1",
        GitPythonCheckConfig,
        git_python_check,
        name="Git Python function verification",
        description="Read admitted Git source and compare evaluation against trusted answers",
        input_model=CheckProgramInput,
        result_model=CheckProgramResult,
    ),
)
