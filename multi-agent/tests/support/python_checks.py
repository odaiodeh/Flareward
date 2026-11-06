"""Controlled Python source and typed check inputs; no process or transport ownership."""

from mas.application.verification.program_checks import CheckProgramInput
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_bundles import BundleEntry, ElementBundle, ResourceDefinition, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import ApplicationDefinition, ProgramDefinition
from mas.domain.verification import VerificationSubject
from mas_plugins.testing.contracts import (
    FunctionArguments,
    PythonFunctionConfig,
    PythonFunctionInput,
)
from mas_plugins.testing.program import FunctionCase, PythonFunctionCheckConfig

from support.artifacts import inline_artifact

ADDITION = b"def add(a, b):\n    return a + b\n"
SUBTRACTION = b"def add(a, b):\n    return a - b\n"


def addition_cases(*, timeout_seconds: float = 10) -> PythonFunctionCheckConfig:
    key = ResourceKey(category=ResourceCategory.OPERATION, rid="evaluate")
    return PythonFunctionCheckConfig(
        evaluator=ElementBundle(
            root=key,
            entries=(
                BundleEntry(
                    resource=ResourceDefinition(
                        key=key,
                        type_key="python_function_evaluate",
                        config=PythonFunctionConfig(
                            function="add", timeout_seconds=timeout_seconds
                        ).model_dump(mode="json"),
                    )
                ),
            ),
        ),
        execution=ExecutionSelection(profile="thread"),
        cases=(
            FunctionCase(args=(1, 2), expected=3),
            FunctionCase(args=(-3, 1), expected=-2),
            FunctionCase(args=(0, 0), expected=0),
        ),
    )


def evaluation_input(content: bytes = ADDITION) -> PythonFunctionInput:
    return PythonFunctionInput(
        artifact=inline_artifact(content),
        cases=tuple(
            FunctionArguments(args=case.args, kwargs=case.kwargs) for case in addition_cases().cases
        ),
    )


def python_verifier_definition(
    owner: Identity, profile: str, config: PythonFunctionCheckConfig | None = None
) -> ProgramDefinition:
    configuration = (config or addition_cases()).model_copy(
        update={"execution": ExecutionSelection(profile=profile)}
    )
    return ProgramDefinition(
        program_id="trusted-verifier",
        name="Trusted Python verifier",
        owner=owner,
        implementation=ApplicationDefinition(
            implementation="python_function_check",
            version="1",
            config=configuration.model_dump(mode="json"),
        ),
    )


def python_check_input(content: bytes = ADDITION) -> CheckProgramInput:
    artifact = inline_artifact(content)
    return CheckProgramInput(
        intent_id="a" * 64,
        plan_id="b" * 64,
        check="tests@1",
        subject=VerificationSubject(
            kind="blob-artifact@1", identity=artifact.reference.model_dump(mode="json")
        ),
        artifact=artifact,
    )
