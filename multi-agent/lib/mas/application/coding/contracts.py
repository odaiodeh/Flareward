"""Portable coding work and results; placement belongs to the program runtime."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


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


class CodingAgentError(RuntimeError):
    """A coding invocation failed; diagnostics never include raw CLI output."""


class CodingAgent(Protocol):
    async def execute(self, request: CodingRequest) -> CodingResult: ...
