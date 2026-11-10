"""Shared application-port behavior for actual memory and Mongo adapters."""

import asyncio
from datetime import UTC, datetime

from lumora.services.identity.domain import Identity
from lumora.services.sharing.domain.models import ShareDirection, ShareStatus
from lumora.services.sharing.notifications import ShareNotificationsRepository


async def verify_notification_repository(repository: ShareNotificationsRepository) -> None:
    received = await repository.list(
        Identity.user("BOB"), ShareDirection.RECEIVED, ShareStatus.PENDING, 0, 100
    )
    assert [item.share_id for item in received] == ["latest", "a", "b"]
    assert [
        item.share_id
        for item in await repository.list(
            Identity.user("bob"), ShareDirection.RECEIVED, ShareStatus.PENDING, 1, 1
        )
    ] == ["a"]
    assert [
        item.share_id
        for item in await repository.list(
            Identity.team("bob"), ShareDirection.RECEIVED, None, 0, 100
        )
    ] == ["team"]
    assert not await repository.list(Identity.team("BOB"), ShareDirection.RECEIVED, None, 0, 100)
    assert (
        len(await repository.list(Identity.user("alice"), ShareDirection.SENT, None, 0, 100)) == 6
    )
    detached = await repository.get("a")
    detached.sender_identity.id = "changed"
    detached.authorized_owner_ids.clear()
    assert (await repository.get("a")).sender_identity.id == "alice"
    assert (await repository.get("a")).authorized_owner_ids
    at = datetime.now(UTC)
    decisions = await asyncio.gather(
        repository.transition("a", ShareStatus.DECLINED, at),
        repository.transition("a", ShareStatus.CANCELED, at),
    )
    assert sorted(decisions) == [False, True]
    decided = await repository.get("a")
    assert decided.status in (ShareStatus.DECLINED, ShareStatus.CANCELED)
    if decided.status == ShareStatus.DECLINED:
        assert abs((decided.declined_at - at).total_seconds()) < 0.001
    assert not await repository.transition("closed", ShareStatus.DECLINED, at)
    assert not await repository.transition("missing", ShareStatus.CANCELED, at)
