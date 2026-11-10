"""Controlled Python source and typed check inputs; no process or transport ownership."""

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import ApplicationDefinition, ProgramDefinition
from lumora.resources.domain.bundles import (
    BundleEntry,
    ElementBundle,
    ResourceDefinition,
    ResourceKey,
)
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.models import VerificationSubject
from lumora.services.verification.program_checks import CheckProgramInput
from plugins.testing.contracts import (
    FunctionArguments,
    PythonFunctionConfig,
    PythonFunctionInput,
)
from plugins.testing.programs.python_check import FunctionCase, PythonFunctionCheckConfig
from support.artifacts import inline_artifact, inline_content

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
                        implementation_version="2.0.0",
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
        source=inline_content(content),
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
