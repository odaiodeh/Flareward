"""Review confirmation follows persisted execution ownership, independent of liveness."""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from lumora.executions.service import ExecutionService
from lumora.services.identity.domain import Identity
from lumora.services.reviews.adapters.executions import ExecutionReviews
from lumora.services.reviews.ports import ReviewMissing, ReviewUnavailable


@pytest.mark.parametrize(
    "ancestor,expected", [("review", True), ("wrapper", True), ("root", True), ("sibling", False)]
)
async def test_completed_review_descendant_is_checked_using_owned_records(ancestor, expected):
    owner = Identity.user("owner")
    executions = create_autospec(ExecutionService, instance=True)
    parents = {"review": "wrapper", "wrapper": "root", "root": None}

    async def get(identifier, caller):
        assert caller == owner
        return SimpleNamespace(
            context=SimpleNamespace(root_execution_id="root"),
            parent_execution_id=parents[identifier],
        )

    executions.get.side_effect = get
    assert (
        await ExecutionReviews(executions).contains("review", ancestor, "root", owner) is expected
    )
    executions.is_active.assert_not_awaited()


@pytest.mark.parametrize("fault", ["foreign-root", "cycle", "missing", "forbidden"])
async def test_invalid_or_unavailable_lineage_cannot_confirm_a_review(fault):
    executions = create_autospec(ExecutionService, instance=True)

    async def get(identifier, owner):
        if fault == "missing":
            raise KeyError(identifier)
        if fault == "forbidden":
            raise PermissionError()
        return SimpleNamespace(
            context=SimpleNamespace(
                root_execution_id="foreign" if fault == "foreign-root" else "root"
            ),
            parent_execution_id="review",
        )

    executions.get.side_effect = get
    adapter = ExecutionReviews(executions)
    if fault in {"missing", "forbidden"}:
        with pytest.raises(ReviewUnavailable if fault == "missing" else ReviewMissing):
            await adapter.contains("review", "wrapper", "root", Identity.user("owner"))
    else:
        assert not await adapter.contains("review", "wrapper", "root", Identity.user("owner"))
    assert executions.get.await_count == 1
