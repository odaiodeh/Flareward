"""Review policies use owned persistence, execution and transport capabilities."""

from typing import Protocol

from lumora.executions.domain.models import ExecutionFailure, FailureKind
from lumora.executions.ports import ExecutionError
from lumora.services.identity.domain import Identity
from lumora.services.reviews.contracts import CloseReview, OpenReview
from lumora.services.reviews.domain.models import ReviewRecord


class ReviewMissing(LookupError):
    """Review is absent or not visible to this caller."""


class ReviewConflict(ValueError):
    """The current occurrence cannot accept this decision or mutation."""


class ReviewStorageError(RuntimeError):
    """Review persistence is unavailable or invalid."""


class ReviewCredentialError(PermissionError):
    """Workflow review capability is unavailable, expired or revoked."""


class ReviewUnavailable(ExecutionError):
    def __init__(self) -> None:
        super().__init__(
            ExecutionFailure(
                kind=FailureKind.INFRASTRUCTURE,
                message="Review service is unavailable",
                code="review_unavailable",
                retryable=True,
            )
        )


class ReviewRepository(Protocol):
    async def create(self, review: ReviewRecord) -> bool: ...
    async def get(self, review_id: str) -> ReviewRecord | None: ...
    async def save(self, review: ReviewRecord, *, expected_revision: int) -> bool: ...
    async def inbox(self, reviewer: str, *, after: str, limit: int) -> list[ReviewRecord]: ...
    async def for_execution(
        self, root_execution_id: str, owner: Identity, *, after: str, limit: int
    ) -> list[ReviewRecord]: ...
    async def pending(self, *, after: str, limit: int) -> list[ReviewRecord]: ...
    async def deliveries(self, *, after: str, limit: int) -> list[ReviewRecord]: ...


class ReviewExecutions(Protocol):
    async def active(self, execution_id: str, root_execution_id: str, owner: Identity) -> bool: ...
    async def wake(self, review: ReviewRecord) -> None: ...


class ReviewGateway(Protocol):
    async def open(self, request: OpenReview) -> ReviewRecord: ...
    async def inspect(self, review_id: str) -> ReviewRecord: ...
    async def close(self, request: CloseReview) -> ReviewRecord: ...
