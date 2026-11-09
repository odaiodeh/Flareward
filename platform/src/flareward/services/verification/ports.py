"""Atomic persistence boundary for immutable plans and revision-checked evidence."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from flareward.executions.domain.models import ExecutionFailure, FailureKind
from flareward.executions.ports import ExecutionError
from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import StoredVerificationAccess
from flareward.services.verification.domain.models import VerificationState
from flareward.services.verification.models import StartVerification, VerificationView


class VerificationMissing(LookupError):
    """The requested verification is absent or inaccessible."""


class VerificationConflict(ValueError):
    """An immutable verification intent or check already has a different result."""


class VerificationStorageError(RuntimeError):
    """Verification persistence is unavailable or invalid."""


class VerificationCredentialError(PermissionError):
    """A workflow capability is invalid, expired or revoked."""


class VerificationUnavailable(ExecutionError):
    def __init__(self, message: str = "Verification service is unavailable") -> None:
        super().__init__(
            ExecutionFailure(
                kind=FailureKind.INFRASTRUCTURE,
                message=message,
                code="verification_unavailable",
                retryable=True,
            )
        )


class VerificationGateway(Protocol):
    async def start(self, request: StartVerification) -> VerificationView: ...
    async def inspect(self, plan_id: str) -> VerificationView: ...
    async def cancel(self, plan_id: str) -> VerificationView: ...


class VerificationAccessRepository(Protocol):
    async def create(self, access: StoredVerificationAccess) -> None: ...
    async def ensure(self, access: StoredVerificationAccess) -> StoredVerificationAccess: ...
    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredVerificationAccess | None: ...
    async def list(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[StoredVerificationAccess]: ...
    async def revoke(self, grant_id: str) -> None: ...
    async def pending(self, *, after: str, limit: int) -> Sequence[StoredVerificationAccess]: ...

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool: ...
    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool: ...


class VerificationRepository(Protocol):
    async def create(self, state: VerificationState) -> bool: ...

    async def get(self, plan_id: str) -> VerificationState | None: ...

    async def save(self, state: VerificationState, *, expected_revision: int) -> bool: ...
