"""Shared owner/root/cursor query contracts, independent of persistence technology."""

from datetime import UTC, datetime, timedelta

import pytest

from lumora.services.identity.domain import Identity
from lumora.services.reviews.domain.models import ReviewRecord
from lumora.services.reviews.ports import ReviewMissing, ReviewRepository
from support.reviews import review_request


async def exercise_execution_review_query(repository: ReviewRepository) -> None:
    owner = Identity.user("query-owner")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    for index, identity, root in (
        (1, owner, "root"),
        (2, owner, "root"),
        (3, Identity.team(owner.id), "root"),
        (4, owner, "different-root"),
    ):
        record = ReviewRecord(
            review_id=f"{index:064x}",
            owner=identity,
            root_execution_id=root,
            execution_id="review-run",
            key=str(index),
            policy="release@1",
            reviewers=frozenset({"reviewer"}),
            specification=review_request().specification,
            created_at=now + timedelta(seconds=index),
            expires_at=now + timedelta(hours=1),
        )
        assert await repository.create(record)
    first = await repository.for_execution("root", owner, after="", limit=1)
    assert [value.key for value in first] == ["2"]
    second = await repository.for_execution("root", owner, after=first[0].review_id, limit=1)
    assert [value.key for value in second] == ["1"]
    assert (
        await repository.for_execution("root", Identity.user("stranger"), after="", limit=50) == []
    )
    for foreign_cursor in (f"{3:064x}", f"{4:064x}", "f" * 64):
        with pytest.raises(ReviewMissing):
            await repository.for_execution("root", owner, after=foreign_cursor, limit=50)
