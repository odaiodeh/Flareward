"""Authorize and persist human decisions; engine messages only wake reconciliation."""

import hashlib
import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial

from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import ReviewAction, ReviewActor
from flareward.services.reviews.contracts import (
    CloseReview,
    OpenReview,
    ReviewPolicy,
    ReviewSchema,
    SubmitReview,
)
from flareward.services.reviews.domain.models import ReviewRecord, ReviewResponse, ReviewStatus
from flareward.services.reviews.ports import (
    ReviewConflict,
    ReviewExecutions,
    ReviewMissing,
    ReviewRepository,
)

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        executions: ReviewExecutions,
        policies: Mapping[str, ReviewPolicy],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository, self._executions = repository, executions
        self._policies = {name: policy.model_copy(deep=True) for name, policy in policies.items()}
        self._now = clock or partial(datetime.now, UTC)
        self._cursor = ""
        self._delivery_cursor = ""

    async def open(self, request: OpenReview, actor: ReviewActor) -> ReviewRecord:
        request = OpenReview.model_validate_json(request.model_dump_json())
        scope, owner = actor.scope, actor.identity
        if scope is None or not scope.allows(ReviewAction.OPEN, request.policy):
            raise PermissionError("Execution-bound review creation is not permitted")
        identifier = hashlib.sha256(
            json.dumps(
                [
                    owner.type.value,
                    owner.id,
                    scope.root_execution_id,
                    request.execution_id,
                    request.key,
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        existing = await self._repository.get(identifier)
        if existing is not None:
            self._authorize(existing, actor, ReviewAction.OPEN)
            if (
                existing.policy != request.policy
                or existing.specification.fingerprint != request.specification.fingerprint
            ):
                raise ReviewConflict("Review occurrence already identifies different work")
            return await self._refresh(existing)
        policy = self._policies.get(request.policy)
        if policy is None or not any(identity.owns(owner) for identity in policy.owners):
            raise PermissionError("Review policy is not permitted")
        if request.specification.timeout_seconds > policy.max_timeout_seconds:
            raise ValueError("Review timeout exceeds its policy")
        if not await self._executions.active(request.execution_id, scope.root_execution_id, owner):
            raise ReviewConflict("Review execution is no longer active")
        now = self._now()
        review = ReviewRecord(
            review_id=identifier,
            owner=owner.model_copy(deep=True),
            root_execution_id=scope.root_execution_id,
            execution_id=request.execution_id,
            key=request.key,
            policy=request.policy,
            reviewers=policy.reviewers,
            specification=request.specification,
            created_at=now,
            expires_at=now + timedelta(seconds=request.specification.timeout_seconds),
        )
        if not await self._repository.create(review):
            return await self.open(request, actor)
        return review

    async def inspect(self, review_id: str, actor: ReviewActor) -> ReviewRecord:
        review = await self._get(review_id)
        self._authorize(review, actor, ReviewAction.READ)
        return await self._refresh(review)

    async def for_reviewer(self, review_id: str, reviewer: Identity) -> ReviewRecord:
        review = await self._get(review_id)
        self._reviewer(review, reviewer)
        return await self._refresh(review)

    async def inbox(
        self, reviewer: Identity, *, after: str = "", limit: int = 50
    ) -> list[ReviewRecord]:
        if not reviewer.is_user or not reviewer.id or not 1 <= limit <= 100:
            raise PermissionError("Review inbox requires authenticated human identity")
        records = await self._repository.inbox(reviewer.id, after=after, limit=limit)
        return [await self._refresh(review) for review in records]

    async def for_execution(
        self, root_execution_id: str, owner: Identity, *, after: str = "", limit: int = 50
    ) -> list[ReviewRecord]:
        """Owners inspect their root's reviews; assignment still governs decisions."""
        if not root_execution_id or not 1 <= limit <= 100:
            raise ValueError("Review query requires an execution root and bounded page")
        records = await self._repository.for_execution(
            root_execution_id, owner, after=after, limit=limit
        )
        for review in records:
            self._authorize(review, ReviewActor(owner), ReviewAction.READ)
            if review.root_execution_id != root_execution_id:
                raise ReviewMissing("Review not found")
        return [await self._refresh(review) for review in records]

    async def respond(
        self, review_id: str, request: SubmitReview, reviewer: Identity
    ) -> ReviewRecord:
        request = SubmitReview.model_validate_json(request.model_dump_json())
        for _ in range(64):
            review = await self._get(review_id)
            self._reviewer(review, reviewer)
            previous = review.response
            if previous is not None:
                same_data = json.dumps(
                    previous.data, sort_keys=True, allow_nan=False
                ) == json.dumps(request.data, sort_keys=True, allow_nan=False)
                if (
                    previous.key == request.key
                    and previous.decision == request.decision
                    and previous.issued_by.owns(reviewer)
                    and same_data
                ):
                    return review
                raise ReviewConflict("Review already has a different immutable response")
            review = await self._refresh(review)
            if (
                review.status != ReviewStatus.PENDING
                or review.revision != request.expected_revision
            ):
                raise ReviewConflict("Review is closed or its revision is stale")
            if request.decision not in review.specification.decisions:
                raise ValueError("Review decision is not permitted")
            ReviewSchema.validate_response(review.specification.response_schema, request.data)
            now = self._now()
            if now >= review.expires_at:
                continue
            response = ReviewResponse(
                key=request.key,
                decision=request.decision,
                data=request.data,
                issued_by=reviewer.model_copy(deep=True),
                recorded_at=now,
            )
            updated = review.model_copy(
                update={
                    "status": ReviewStatus.DECIDED,
                    "response": response,
                    "delivery_pending": True,
                    "revision": review.revision + 1,
                }
            )
            if await self._repository.save(updated, expected_revision=review.revision):
                return updated
        raise ReviewConflict("Review changed concurrently; inspect its current revision")

    async def close(self, request: CloseReview, actor: ReviewActor) -> ReviewRecord:
        review = await self._get(request.review_id)
        self._authorize(review, actor, ReviewAction.CLOSE)
        review = await self._refresh(review)
        target = (
            ReviewStatus.SUPERSEDED if request.superseded_by is not None else ReviewStatus.CANCELLED
        )
        if review.status == target and review.superseded_by == request.superseded_by:
            return review
        if review.status != ReviewStatus.PENDING or review.revision != request.expected_revision:
            raise ReviewConflict("Review is closed or its revision is stale")
        if request.superseded_by is not None:
            replacement = await self._get(request.superseded_by)
            self._authorize(replacement, actor, ReviewAction.READ)
            if (
                replacement.review_id == review.review_id
                or replacement.root_execution_id != review.root_execution_id
            ):
                raise ReviewConflict("Replacement review does not belong to this workflow")
        updated = review.model_copy(
            update={
                "status": target,
                "superseded_by": request.superseded_by,
                "delivery_pending": True,
                "revision": review.revision + 1,
            }
        )
        if not await self._repository.save(updated, expected_revision=review.revision):
            raise ReviewConflict("Review changed concurrently; inspect its current revision")
        return updated

    async def reconcile(self, limit: int = 50) -> None:
        pending = await self._repository.pending(after=self._cursor, limit=limit)
        if not pending:
            self._cursor = ""
        for review in pending:
            self._cursor = review.review_id
            try:
                await self._refresh(review)
            except Exception:
                logger.exception("Review lifecycle reconciliation failed for %s", review.review_id)
        deliveries = await self._repository.deliveries(after=self._delivery_cursor, limit=limit)
        if not deliveries:
            self._delivery_cursor = ""
        for review in deliveries:
            self._delivery_cursor = review.review_id
            try:
                if await self._executions.active(
                    review.execution_id, review.root_execution_id, review.owner
                ):
                    await self._executions.wake(review)
                await self._repository.save(
                    review.model_copy(
                        update={"delivery_pending": False, "revision": review.revision + 1}
                    ),
                    expected_revision=review.revision,
                )
            except Exception:
                logger.exception("Review delivery remains pending for %s", review.review_id)

    async def _refresh(self, review: ReviewRecord) -> ReviewRecord:
        for _ in range(64):
            if review.status != ReviewStatus.PENDING:
                return review
            if self._now() >= review.expires_at:
                status = ReviewStatus.EXPIRED
            elif not await self._executions.active(
                review.execution_id, review.root_execution_id, review.owner
            ):
                status = ReviewStatus.CANCELLED
            else:
                return review
            updated = review.model_copy(
                update={"status": status, "delivery_pending": True, "revision": review.revision + 1}
            )
            if await self._repository.save(updated, expected_revision=review.revision):
                return updated
            review = await self._get(review.review_id)
        raise ReviewConflict("Review lifecycle changed concurrently")

    async def _get(self, review_id: str) -> ReviewRecord:
        review = await self._repository.get(review_id)
        if review is None:
            raise ReviewMissing("Review not found")
        return review

    @staticmethod
    def _authorize(review: ReviewRecord, actor: ReviewActor, action: ReviewAction) -> None:
        if not review.owner.owns(actor.identity) or (
            actor.scope is not None
            and (
                actor.scope.root_execution_id != review.root_execution_id
                or review.policy not in actor.scope.policies
            )
        ):
            raise ReviewMissing("Review not found")
        if actor.scope is not None and not actor.scope.allows(action, review.policy):
            raise PermissionError("Review action is not permitted")

    @staticmethod
    def _reviewer(review: ReviewRecord, reviewer: Identity) -> None:
        if not reviewer.is_user or reviewer.id not in review.reviewers:
            raise ReviewMissing("Review not found")
