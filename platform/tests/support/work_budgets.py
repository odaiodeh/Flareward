"""Shared storage contract for concurrent, immutable root-wide work allowances."""

import asyncio

import pytest

from lumora.executions.budgets import WorkBudgetRepository
from lumora.executions.domain.budgets import (
    WorkBudget,
    WorkBudgetConflict,
    WorkKind,
    WorkLimitExceeded,
    WorkLimits,
    WorkReservation,
)
from lumora.services.identity.domain import Identity


def work_budget(root: str = "root", **limits: int) -> WorkBudget:
    return WorkBudget(
        root_execution_id=root, owner=Identity.user("owner"), limits=WorkLimits(**limits)
    )


def work_reservation(
    key: str, *, kind: WorkKind = WorkKind.DISPATCH, execution: str = "root", depth: int = 0
) -> WorkReservation:
    return WorkReservation(
        execution_id=execution, key=key, kind=kind, depth=depth, fingerprint="a" * 64
    )


async def assert_work_budget_contract(
    repository: WorkBudgetRepository, peer: WorkBudgetRepository
) -> None:
    budget = work_budget(max_dispatches=2, max_children=1, max_depth=1)
    with pytest.raises(WorkBudgetConflict):
        await repository.reserve(budget, work_reservation("uninitialized"))
    await asyncio.gather(repository.initialize(budget), peer.initialize(budget))
    for different in (
        budget.model_copy(update={"owner": Identity.user("other")}),
        budget.model_copy(update={"limits": WorkLimits(max_dispatches=100)}),
    ):
        with pytest.raises(WorkBudgetConflict):
            await peer.initialize(different)
        with pytest.raises(WorkBudgetConflict):
            await peer.reserve(different, work_reservation("unauthorized"))
    duplicate = work_reservation("once")
    await asyncio.gather(*(repo.reserve(budget, duplicate) for repo in [repository, peer] * 10))
    assert (await peer.usage(budget)).dispatches == 1
    with pytest.raises(WorkBudgetConflict):
        await peer.reserve(budget, duplicate.model_copy(update={"fingerprint": "b" * 64}))
    with pytest.raises(WorkLimitExceeded, match="max_depth"):
        await peer.reserve(budget, work_reservation("deep", depth=2))
    outcomes = await asyncio.gather(
        *(
            repo.reserve(budget, work_reservation(str(index), execution="child", depth=1))
            for index, repo in enumerate([repository, peer] * 10)
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, WorkLimitExceeded) for outcome in outcomes) == 19
    await peer.reserve(budget, work_reservation("child", kind=WorkKind.CHILD, depth=1))
    with pytest.raises(WorkLimitExceeded, match="max_children"):
        await repository.reserve(budget, work_reservation("another-child", kind=WorkKind.CHILD))
    assert (await peer.reserve(budget, duplicate)).dispatches == 2
    usage = await peer.usage(budget)
    assert (usage.dispatches, usage.children) == (2, 1)
    isolated = work_budget("independent", max_dispatches=1)
    await peer.initialize(isolated)
    assert (await peer.reserve(isolated, duplicate)).dispatches == 1
