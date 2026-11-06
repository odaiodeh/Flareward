"""Admission failure never dispatches work or blocks the explicit cancellation path."""

from unittest.mock import create_autospec

import pytest
from inbound.run_engine.interactions import cancel_waits
from inbound.run_engine.programs import execute_program
from mas.core.identity import Identity
from mas.domain.execution.budgets import WorkLimits
from mas.domain.execution.context import ExecutionContext
from outbound.run_engine.budgets import BudgetedOperations
from run_engine.models import WorkBudgetBinding
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import FunctionRef
from runengine.invocation.errors import InvocationContractError, InvocationInfrastructureError
from runengine.invocation.models import InvocationOutcome, InvocationRequest

from bootstrap.work_budgets import admit_work


@pytest.mark.parametrize("operation", ["execute", "invoke", "start_child"])
@pytest.mark.parametrize("unavailable", [False, True])
async def test_admission_denial_or_unavailable_storage_cannot_dispatch(operation, unavailable):
    operations = create_autospec(CoordinationOperations, instance=True)
    error = (
        InvocationInfrastructureError("Admission unavailable")
        if unavailable
        else InvocationContractError("Execution-tree work limit exceeded")
    )
    operations.invoke.side_effect = error
    budgeted = BudgetedOperations(
        operations,
        WorkBudgetBinding(
            limits=WorkLimits(max_dispatches=0), admission=FunctionRef.from_callable(admit_work)
        ),
        ExecutionContext(
            identity=Identity.user("owner"), execution_id="root", root_execution_id="root"
        ),
    )
    request = InvocationRequest.create(cancel_waits)
    if operation == "execute" and not unavailable:
        outcome = await budgeted.execute(request)
        assert outcome.failure is not None and outcome.failure.origin == "contract"
    else:
        with pytest.raises(type(error)):
            if operation == "start_child":
                await budgeted.start_child(
                    RunRequest.create(execute_program, input={}), key="child"
                )
            else:
                await getattr(budgeted, operation)(request)
    operations.execute.assert_not_awaited()
    operations.start_child.assert_not_awaited()


async def test_published_cancellation_receiver_is_exempt_from_spending_work():
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.execute.return_value = InvocationOutcome.from_value(None)
    cancellation = FunctionRef.from_callable(cancel_waits)
    budgeted = BudgetedOperations(
        operations,
        WorkBudgetBinding(
            limits=WorkLimits(max_dispatches=0), admission=FunctionRef.from_callable(admit_work)
        ),
        ExecutionContext(
            identity=Identity.user("owner"), execution_id="root", root_execution_id="root"
        ),
        cancellation,
    )
    assert await budgeted.invoke(InvocationRequest(function=cancellation)) is None
    operations.invoke.assert_not_awaited()
    operations.execute.assert_awaited_once()
