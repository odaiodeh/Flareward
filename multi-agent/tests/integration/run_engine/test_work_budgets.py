"""Root allowances span graph -> Map -> graph -> real typed operations."""

from dataclasses import dataclass

import pytest
from mas.application.execution.service import ExecutionService
from mas.application.programs.composition.programs import APPLICATION_PROGRAMS
from mas.application.programs.service import ProgramService
from mas.core.identity import Identity
from mas.domain.execution.budgets import WorkBudget, WorkLimits
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import ApplicationDefinition
from outbound.mongo.work_budgets import MongoWorkBudgets
from support.composition import composition_graph, mapped_program
from support.operations import operation_bundle, operation_graph
from support.scenarios import publish, run

from bootstrap.platform import compose_platform


@dataclass(frozen=True)
class BudgetPlatform:
    programs: ProgramService
    executions: ExecutionService
    owner: Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "override", [{}, {"max_dispatches": 1}, {"max_children": 2}, {"max_depth": 1}]
)
async def test_shared_budget_across_concurrent_nested_graph_and_backend_programs(
    application, secret_settings, mongo_database, profile, override
):
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    limits = WorkLimits.model_validate(
        {"max_dispatches": 2, "max_children": 3, "max_depth": 2, **override}
    )
    settings = secret_settings.model_copy(update={"work_limits": limits})
    async with compose_platform(
        settings, elements=application.elements, applications=application.applications
    ) as services:
        platform = BudgetPlatform(services.programs, services.executions, application.owner)
        body = await publish(platform, "body", operation_graph(profile))
        mapped = await publish(platform, "mapped", mapped_program(body.reference))
        root = await publish(platform, "root", composition_graph(mapped.reference))
        execution = await run(platform, root, {"items": ["one", "two"]})
        assert execution.work_limits == limits
        budget = WorkBudget(
            root_execution_id=execution.execution_id, owner=platform.owner, limits=limits
        )
        repository = MongoWorkBudgets(mongo_database)
        usage = await repository.usage(budget)
        assert usage.dispatches <= limits.max_dispatches and usage.children <= limits.max_children
        if not override:
            assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
            assert (usage.dispatches, usage.children) == (2, 3)
            assert [item["value"]["answer"] for item in execution.result["result"]["items"]] == [
                "typed:middle:one",
                "typed:middle:two",
            ]
            child = (await platform.executions.children(execution.execution_id, platform.owner))[0]
            assert child.work_limits == limits
            leaves = await platform.executions.children(child.execution_id, platform.owner)
            assert len(leaves) == 2 and all(leaf.work_limits == limits for leaf in leaves)
        else:
            assert execution.phase == ExecutionPhase.FAILED, execution
            assert execution.failure.kind == "contract", execution.failure
            assert "work limit exceeded" in execution.failure.message
        # Public retries of the original root submission do not spend again.
        await run(platform, root, {"items": ["one", "two"]}, execution_id=execution.execution_id)
        assert await repository.usage(budget) == usage


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_backend_operation_cannot_bypass_zero_root_dispatch_allowance(
    application, secret_settings, mongo_database, profile
):
    limits = WorkLimits(max_dispatches=0)
    settings = secret_settings.model_copy(update={"work_limits": limits})
    async with compose_platform(
        settings, elements=application.elements, applications=application.applications
    ) as services:
        platform = BudgetPlatform(services.programs, services.executions, application.owner)
        body = ApplicationDefinition(
            implementation="operation",
            version="1",
            config={"bundle": operation_bundle(application.elements).model_dump(mode="json")},
        )
        revision = await publish(platform, "backend-operation", body, execution_profile=profile)
        execution = await run(platform, revision, {"text": "not-dispatched"})
        assert execution.phase == ExecutionPhase.FAILED and execution.failure.kind == "contract", (
            execution.failure
        )
        assert execution.failure.code == "WORK_LIMIT_EXCEEDED"
        budget = WorkBudget(
            root_execution_id=execution.execution_id, owner=platform.owner, limits=limits
        )
        assert (await MongoWorkBudgets(mongo_database).usage(budget)).dispatches == 0
