"""Trusted comparison coordinated independently of candidate operation placement."""

import json
from typing import Self

from pydantic import BaseModel, Field, JsonValue, model_validator

from flareward.executions.domain.preferences import ExecutionSelection
from flareward.models import Model
from flareward.programs.ports import ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import ElementBundle
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.artifacts.domain.models import ContentIdentity, InlineContent
from flareward.services.verification.domain.models import CheckVerdict, VerificationSubject
from flareward.services.verification.program_checks import CheckProgramInput, CheckProgramResult
from plugins.testing.contracts import (
    EvaluationFailure,
    FunctionArguments,
    PythonFunctionInput,
    PythonFunctionResult,
)


class FunctionCase(FunctionArguments):
    expected: JsonValue


class PythonFunctionCheckConfig(Model):
    evaluator: ElementBundle
    cases: tuple[FunctionCase, ...] = Field(min_length=1, max_length=32)
    execution: ExecutionSelection

    @model_validator(mode="after")
    def valid_comparison(self) -> Self:
        if self.evaluator.root.category != ResourceCategory.OPERATION:
            raise ValueError("Python verification requires an evaluation operation")
        if sum(len(case.model_dump_json().encode()) for case in self.cases) > 65_536:
            raise ValueError("Python check cases exceed their byte limit")
        return self


class PythonFunctionCheck:
    """Expected results and check authority never enter the candidate invocation."""

    def __init__(self, runtime: ProgramRuntime, config: PythonFunctionCheckConfig) -> None:
        self._runtime, self._config = runtime, config

    @staticmethod
    def _error(request: CheckProgramInput, reason: EvaluationFailure) -> CheckProgramResult:
        return CheckProgramResult(
            subject_fingerprint=request.subject.fingerprint,
            verdict=CheckVerdict.ERROR,
            details={"reason": reason.value},
        )

    def _compare(
        self, request: CheckProgramInput, result: PythonFunctionResult
    ) -> CheckProgramResult:
        if result.failure is not None:
            return self._error(request, result.failure)
        if result.values is None or len(result.values) != len(self._config.cases):
            return self._error(request, EvaluationFailure.OUTPUT)
        failures: list[JsonValue] = []
        for index, (value, case) in enumerate(zip(result.values, self._config.cases, strict=True)):
            if json.dumps(value, sort_keys=True, allow_nan=False) != json.dumps(
                case.expected, sort_keys=True, allow_nan=False
            ):
                failures.append({"case": index, "expected": case.expected, "actual": value})
        compared = CheckProgramResult(
            subject_fingerprint=request.subject.fingerprint,
            verdict=CheckVerdict.FAILED if failures else CheckVerdict.PASSED,
            details={"cases": len(result.values), "failures": failures},
        )
        if len(compared.model_dump_json().encode()) > 65_536:
            return self._error(request, EvaluationFailure.OUTPUT)
        return compared

    async def run(self, request: CheckProgramInput) -> CheckProgramResult:
        artifact = request.artifact
        if (
            request.subject.kind != "blob-artifact@1"
            or artifact is None
            or VerificationSubject(
                kind="blob-artifact@1", identity=artifact.reference.model_dump(mode="json")
            ).fingerprint
            != request.subject.fingerprint
        ):
            raise ValueError("Python checks require the exact admitted candidate content")
        return await self.evaluate(
            request,
            InlineContent(
                identity=ContentIdentity(
                    sha256=artifact.reference.sha256, size_bytes=artifact.reference.size_bytes
                ),
                data=artifact.data,
            ),
        )

    async def evaluate(
        self, request: CheckProgramInput, source: InlineContent
    ) -> CheckProgramResult:
        """Evaluate bytes already bound to the subject by this trusted coordinator."""
        inputs = PythonFunctionInput(
            source=source,
            cases=tuple(
                FunctionArguments(args=case.args, kwargs=case.kwargs) for case in self._config.cases
            ),
        )
        actual = await self._runtime.invoke_element(
            self._config.evaluator,
            inputs.model_dump(mode="json"),
            key="evaluate",
            execution=self._config.execution,
        )
        try:
            return self._compare(request, PythonFunctionResult.model_validate(actual))
        except ValueError:
            return self._error(request, EvaluationFailure.OUTPUT)


async def python_function_check(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, PythonFunctionCheckConfig)
    request = CheckProgramInput.model_validate(inputs)
    return (await PythonFunctionCheck(runtime, config).run(request)).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "python_function_check",
        "1",
        PythonFunctionCheckConfig,
        python_function_check,
        name="Python function verification",
        description="Compare isolated candidate results against pinned expected answers",
        input_model=CheckProgramInput,
        result_model=CheckProgramResult,
    ),
)
