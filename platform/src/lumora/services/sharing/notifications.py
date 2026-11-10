"""Invitation queries and atomic decisions, separate from resource-copy orchestration."""

from datetime import UTC, datetime
from typing import Protocol

from lumora.services.identity.domain import Identity
from lumora.services.sharing.domain.models import (
    ShareDirection,
    ShareInvite,
    ShareStatus,
    matches_share_identity,
)


class ShareMissing(KeyError):
    pass


class ShareConflict(RuntimeError):
    pass


class ShareStorageError(RuntimeError):
    pass


class ShareNotificationsRepository(Protocol):
    async def get(self, share_id: str) -> ShareInvite: ...
    async def list(
        self,
        caller: Identity,
        direction: ShareDirection,
        status: ShareStatus | None,
        offset: int,
        limit: int,
    ) -> list[ShareInvite]: ...
    async def transition(self, share_id: str, status: ShareStatus, at: datetime) -> bool:
        """Change pending to declined/canceled atomically; return whether this attempt won."""
        ...


class ShareNotifications:
    def __init__(self, repository: ShareNotificationsRepository) -> None:
        self._repository = repository

    async def list(
        self,
        caller: Identity,
        *,
        direction: ShareDirection = ShareDirection.RECEIVED,
        status: ShareStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ShareInvite]:
        if offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("Invalid invitation pagination")
        return await self._repository.list(caller, direction, status, offset, limit)

    async def get(self, share_id: str, caller: Identity) -> ShareInvite:
        invite = await self._repository.get(share_id)
        if not any(
            matches_share_identity(identity, caller)
            for identity in (invite.sender_identity, invite.recipient_identity)
        ):
            raise PermissionError("Access denied")
        return invite

    async def decline(self, share_id: str, caller: Identity) -> None:
        await self._decide(share_id, caller, ShareStatus.DECLINED)

    async def cancel(self, share_id: str, caller: Identity) -> None:
        await self._decide(share_id, caller, ShareStatus.CANCELED)

    async def _decide(self, share_id: str, caller: Identity, target: ShareStatus) -> None:
        invite = await self._repository.get(share_id)
        identity = (
            invite.recipient_identity if target == ShareStatus.DECLINED else invite.sender_identity
        )
        if not matches_share_identity(identity, caller):
            raise PermissionError("Access denied")
        if invite.status == target:
            return
        if invite.status != ShareStatus.PENDING:
            raise ShareConflict("Invitation is no longer pending")
        if not await self._repository.transition(share_id, target, datetime.now(UTC)):
            # A repeated identical decision is idempotent; a competing outcome is a conflict.
            current = await self._repository.get(share_id)
            if current.status != target:
                raise ShareConflict("Invitation is no longer pending")
