"""Application runtime ports expose application failures rather than SDK exceptions."""

from unittest.mock import create_autospec

import pytest
from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.execution.models import FailureKind
from mas.execution.ports import ExecutionError
from outbound.run_engine.runtime import ChildProgramExecution, RunEngineProgramRuntime
from runengine.coordination.ports import CoordinationOperations, RunHandle
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError
from support.scenarios import bundle


@pytest.mark.parametrize("operation", ["invoke", "receive", "sleep"])
async def test_runtime_translates_infrastructure_failure_at_each_application_port(operation):
    operations = create_autospec(CoordinationOperations, instance=True)
    getattr(operations, operation).side_effect = InvocationInfrastructureError(
        "Native transport failure", retryable=True
    )
    runtime = RunEngineProgramRuntime(
        operations, {}, (), ExecutionContext(identity=Identity.user("owner")), None
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
