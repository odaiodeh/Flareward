"""Portable coding work and results; placement belongs to the program runtime."""

from pathlib import PurePosixPath
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flareward.executions.domain.context import ExecutionContext
from flareward.services.workspaces.domain.files import InlineFile, InputFile


class CodingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt: str = Field(min_length=1, max_length=65_536)
    context: str = Field(default="", max_length=65_536)
    files: tuple[InputFile, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def distinct_destinations(self) -> Self:
        paths = [str(PurePosixPath(file.path)) for file in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("Coding input files require distinct destination paths")
        if (
            sum(
                file.content.identity.size_bytes
                for file in self.files
                if isinstance(file, InlineFile)
            )
            > 1_048_576
        ):
            raise ValueError("Coding inline files exceed their aggregate byte limit")
        return self


class CodingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt: str = Field(min_length=1, max_length=65_536)
    workspace: str = Field(min_length=1)


class CodingUsage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


class CodingResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str
    usage: CodingUsage = Field(default_factory=CodingUsage)
    commands: int = Field(default=0, ge=0)
    changes: int = Field(default=0, ge=0)


class CodingOutcome(CodingResult):
    """The executed coding result plus its receiver-relative workspace binding."""

    workspace: str = Field(min_length=1)


class CodingAgentError(RuntimeError):
    """A coding invocation failed; diagnostics never include raw CLI output."""


class CodingAgent(Protocol):
    async def execute(self, request: CodingRequest) -> CodingResult: ...


class WorkspacePreparation(Protocol):
    async def prepare(
        self, files: tuple[InputFile, ...], workspace: str, context: ExecutionContext
    ) -> None: ...
