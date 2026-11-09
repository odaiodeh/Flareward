"""Review policy and application-port doubles shared without HTTP, SDK or database imports."""

import asyncio
from datetime import datetime

from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import (
    ReviewAction,
    ReviewActor,
    ReviewScope,
    StoredReviewGrant,
)
from flareward.services.reviews.contracts import OpenReview, ReviewPolicy, ReviewSettings
from flareward.services.reviews.domain.models import ReviewRecord, ReviewStatus
from flareward.services.reviews.ports import ReviewMissing, ReviewUnavailable


class MemoryReviews:
    def __init__(self) -> None:
        self.records: dict[str, ReviewRecord] = {}
        self.fail_delivery_ack = False

    async def create(self, review: ReviewRecord) -> bool:
        if review.review_id in self.records:
            return False
        self.records[review.review_id] = review.model_copy(deep=True)
        return True

    async def get(self, review_id: str) -> ReviewRecord | None:
        await asyncio.sleep(0)
        value = self.records.get(review_id)
        return value.model_copy(deep=True) if value else None

    async def save(self, review: ReviewRecord, *, expected_revision: int) -> bool:
        await asyncio.sleep(0)
        if (
            self.fail_delivery_ack
            and review.status != ReviewStatus.PENDING
            and not review.delivery_pending
        ):
            raise ReviewUnavailable()
        current = self.records.get(review.review_id)
        if current is None or current.revision != expected_revision:
            return False
        self.records[review.review_id] = review.model_copy(deep=True)
        return True

    async def inbox(self, reviewer: str, *, after: str, limit: int) -> list[ReviewRecord]:
        return self._page(
            [value for value in self.records.values() if reviewer in value.reviewers], after, limit
        )

    async def for_execution(
        self, root_execution_id: str, owner: Identity, *, after: str, limit: int
    ) -> list[ReviewRecord]:
        return self._page(
            [
                value
                for value in self.records.values()
                if value.owner.owns(owner) and value.root_execution_id == root_execution_id
            ],
            after,
            limit,
        )

    @staticmethod
    def _page(records: list[ReviewRecord], after: str, limit: int) -> list[ReviewRecord]:
        reviews = sorted(
            records,
            key=lambda item: (-item.created_at.timestamp(), item.review_id),
        )
        if after and not any(item.review_id == after for item in reviews):
            raise ReviewMissing("Review cursor not found")
        start = (
            next((index + 1 for index, item in enumerate(reviews) if item.review_id == after), 0)
            if after
            else 0
        )
        return [review.model_copy(deep=True) for review in reviews[start : start + limit]]

    async def pending(self, *, after: str, limit: int) -> list[ReviewRecord]:
        return [
            value.model_copy(deep=True)
            for key, value in sorted(self.records.items())
            if key > after and value.status == ReviewStatus.PENDING
        ][:limit]

    async def deliveries(self, *, after: str, limit: int) -> list[ReviewRecord]:
        return [
            value.model_copy(deep=True)
            for key, value in sorted(self.records.items())
            if key > after and value.delivery_pending
        ][:limit]


class MemoryReviewAccess:
    def __init__(self) -> None:
        self.records: dict[str, StoredReviewGrant] = {}

    async def create(self, access: StoredReviewGrant) -> None:
        self.records[access.grant.grant_id] = access.model_copy(deep=True)

    async def ensure(self, access: StoredReviewGrant) -> StoredReviewGrant:
        return self.records.setdefault(access.grant.grant_id, access).model_copy(deep=True)

    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredReviewGrant | None:
        record = self.records.get(grant_id)
        if (
            record is not None
            and active_at is not None
            and (record.grant.revoked or record.grant.expires_at <= active_at)
        ):
            return None
        return record

    async def revoke(self, grant_id: str) -> None:
        current = self.records[grant_id]
        self.records[grant_id] = current.model_copy(
            update={"grant": current.grant.model_copy(update={"revoked": True})}
        )

    async def pending(self, *, after: str, limit: int) -> list[StoredReviewGrant]:
        return [
            stored
            for key, stored in sorted(self.records.items())
            if key > after and not stored.grant.revoked
        ][:limit]

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        current = self.records[grant_id]
        if (
            current.grant.revoked
            or current.grant.expires_at != expected_expiry
            or expected_expiry > now
        ):
            return False
        await self.revoke(grant_id)
        return True

    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool:
        current = self.records[grant_id]
        grant = current.grant
        if (
            grant.revoked
            or grant.expires_at != expected_expiry
            or grant.renewal is None
            or grant.renewal.next_expiry(now, expected_expiry) != expires_at
        ):
            return False
        self.records[grant_id] = current.model_copy(
            update={"grant": grant.model_copy(update={"expires_at": expires_at})}
        )
        return True


class ReviewExecutions:
    def __init__(self) -> None:
        self.executions = {("root", "root"), ("review-run", "root")}
        self.messages: list[str] = []
        self.lose_ack = False

    async def active(self, execution_id: str, root_execution_id: str, owner: Identity) -> bool:
        return (execution_id, root_execution_id) in self.executions

    async def wake(self, review: ReviewRecord) -> None:
        self.messages.append(review.review_id)
        if self.lose_ack:
            raise ReviewUnavailable()


def review_policy(owner: Identity) -> ReviewPolicy:
    return ReviewPolicy(
        owners=(owner,), reviewers=frozenset({"reviewer"}), max_timeout_seconds=3600
    )


def review_actor(owner: Identity) -> ReviewActor:
    return ReviewActor(
        owner,
        ReviewScope(
            root_execution_id="root",
            policies=frozenset({"release@1"}),
            actions=frozenset(ReviewAction),
        ),
    )


def review_request(key: str = "review") -> OpenReview:
    return OpenReview(
        key=key,
        execution_id="review-run",
        policy="release@1",
        specification=ReviewSettings(
            prompt="Review this exact candidate",
            subject={"candidate": "immutable-candidate"},
            response_schema={
                "type": "object",
                "properties": {"feedback": {"type": "string"}},
                "required": ["feedback"],
                "additionalProperties": False,
            },
            timeout_seconds=60,
        ),
    )
