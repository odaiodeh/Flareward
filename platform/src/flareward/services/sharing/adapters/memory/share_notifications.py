"""Independent invitation snapshots with atomic pending decisions."""

import asyncio
from collections.abc import Iterable
from datetime import datetime

from flareward.services.identity.domain import Identity
from flareward.services.sharing.domain.models import (
    ShareDirection,
    ShareInvite,
    ShareStatus,
    matches_share_identity,
)
from flareward.services.sharing.notifications import ShareMissing


class MemoryShareNotifications:
    def __init__(self, invitations: Iterable[ShareInvite] = ()) -> None:
        self._records = {invite.share_id: invite.model_dump_json() for invite in invitations}
        self._lock = asyncio.Lock()

    async def get(self, share_id: str) -> ShareInvite:
        try:
            return ShareInvite.model_validate_json(self._records[share_id])
        except KeyError:
            raise ShareMissing("Invitation not found") from None

    async def list(
        self,
        caller: Identity,
        direction: ShareDirection,
        status: ShareStatus | None,
        offset: int,
        limit: int,
    ) -> list[ShareInvite]:
        values = [ShareInvite.model_validate_json(value) for value in self._records.values()]
        matching = [
            invite
            for invite in values
            if matches_share_identity(invite.participant(direction), caller)
            and (status is None or invite.status == status)
        ]
        # Stable ties are needed for pagination, including legacy records sharing a timestamp.
        matching.sort(key=lambda invite: invite.share_id)
        matching.sort(key=lambda invite: invite.created_at, reverse=True)
        return matching[offset : offset + limit]

    async def transition(self, share_id: str, status: ShareStatus, at: datetime) -> bool:
        if status not in (ShareStatus.DECLINED, ShareStatus.CANCELED):
            raise ValueError("Unsupported invitation decision")
        async with self._lock:
            try:
                invite = await self.get(share_id)
            except ShareMissing:
                return False
            if invite.status != ShareStatus.PENDING:
                return False
            invite.status = status
            if status == ShareStatus.DECLINED:
                invite.declined_at = at
            self._records[share_id] = invite.model_dump_json()
            return True
