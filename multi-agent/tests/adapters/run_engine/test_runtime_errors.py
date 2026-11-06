"""Application runtime ports expose application failures rather than SDK exceptions."""

from unittest.mock import create_autospec

import pytest
from mas.application.execution.ports import ExecutionError
from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.models import ExecutionFailure, FailureKind
from outbound.run_engine.errors import application_errors
from outbound.run_engine.runtime import ChildProgramExecution, RunEngineProgramRuntime
from run_engine.models import ElementSpecifications, ProgramPlacement
from runengine.coordination.ports import CoordinationOperations, RunHandle
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError
from support.elements import element_registry
from support.scenarios import bundle


@pytest.mark.parametrize("operation", ["invoke", "receive", "sleep"])
async def test_runtime_translates_infrastructure_failure_at_each_application_port(operation):
    operations = create_autospec(CoordinationOperations, instance=True)
    getattr(operations, operation).side_effect = InvocationInfrastructureError(
        "Native transport failure", retryable=True
    )
    runtime = RunEngineProgramRuntime(
        operations,
        {},
        ElementSpecifications.from_registry(element_registry()),
        ExecutionContext(identity=Identity.user("owner")),
        ProgramPlacement(default_profile="thread", profiles={"thread": {"runner_type": "thread"}}),
    )
    with pytest.raises(ExecutionError) as error:
        if operation == "invoke":
            await runtime.invoke_element(bundle(), {}, key="work")
        elif operation == "receive":
            await runtime.receive("input")
        else:
            await runtime.sleep(1)
    assert error.value.failure.kind == FailureKind.INFRASTRUCTURE
    assert error.value.failure.retryable is True


async def test_child_handle_translates_native_contract_failure():
    handle = create_autospec(RunHandle, instance=True)
    handle.result.side_effect = InvocationContractError("Invalid child output")
    with pytest.raises(ExecutionError) as error:
        await ChildProgramExecution(handle).result()
    assert error.value.failure.kind == FailureKind.CONTRACT


@application_errors
async def rejected_application_call(failure: ExecutionFailure) -> None:
    raise ExecutionError(failure)


@pytest.mark.parametrize("kind", [FailureKind.CONTRACT, FailureKind.INFRASTRUCTURE])
async def test_application_error_translation_preserves_classification_and_machine_code(kind):
    failure = ExecutionFailure(
        kind=kind, message="Safe refusal", code="CONTROL_REFUSED", retryable=False
    )
    expected = (
        InvocationContractError if kind == FailureKind.CONTRACT else InvocationInfrastructureError
    )
    with pytest.raises(expected) as error:
        await rejected_application_call(failure)
    assert error.value.failure.code == "CONTROL_REFUSED"
    assert error.value.failure.origin == kind
