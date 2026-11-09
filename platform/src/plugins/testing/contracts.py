"""Portable candidate evaluation data, without verification authority or answers."""

from enum import StrEnum
from typing import Self

from pydantic import Field, JsonValue, model_validator

from flareward.models import Model
from flareward.services.artifacts.domain.models import InlineContent


class FunctionArguments(Model):
    args: tuple[JsonValue, ...] = Field(default=(), max_length=32)
    kwargs: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)


class PythonFunctionConfig(Model):
    function: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    timeout_seconds: float = Field(default=10, ge=0.1, le=300, allow_inf_nan=False)


class PythonFunctionInput(Model):
    source: InlineContent
    cases: tuple[FunctionArguments, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def bounded_cases(self) -> Self:
        if sum(len(case.model_dump_json().encode()) for case in self.cases) > 65_536:
            raise ValueError("Python function arguments exceed their byte limit")
        return self


class EvaluationFailure(StrEnum):
    DEADLINE = "deadline_exceeded"
    EXECUTION = "execution_failed"
    OUTPUT = "invalid_or_excessive_output"


class PythonFunctionResult(Model):
    values: tuple[JsonValue, ...] | None = Field(default=None, max_length=32)
    failure: EvaluationFailure | None = None

    @model_validator(mode="after")
    def one_bounded_outcome(self) -> Self:
        if (self.values is None) == (self.failure is None):
            raise ValueError("Evaluation requires values or a failure")
        if len(self.model_dump_json().encode()) > 65_536:
            raise ValueError("Python function results exceed their byte limit")
        return self
