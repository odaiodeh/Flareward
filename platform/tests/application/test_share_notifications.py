"""Sharing policy uses only its own storage port and portable domain values."""

import asyncio
from unittest.mock import ANY, create_autospec

import pytest
from support.sharing import invitation

from lumora.services.identity.domain import Identity
from lumora.services.sharing.domain.models import ShareStatus
from lumora.services.sharing.notifications import (
    ShareConflict,
    ShareNotifications,
    ShareNotificationsRepository,
)


@pytest.fixture
def repository():
    return create_autospec(ShareNotificationsRepository, instance=True, spec_set=True)


async def test_queries_authorize_participants_and_reject_type_collisions(repository):
    repository.get.return_value = invitation()
    service = ShareNotifications(repository)
    assert (await service.get("invite", Identity.user("ALICE"))).share_id == "invite"
    assert (await service.get("invite", Identity.user("bob"))).share_id == "invite"
    for caller in (Identity.user("mallory"), Identity.team("alice")):
        with pytest.raises(PermissionError, match="Access denied"):
            await service.get("invite", caller)
    with pytest.raises(ValueError, match="pagination"):
        await service.list(Identity.user("alice"), limit=0)
    repository.list.assert_not_called()


@pytest.mark.parametrize(
    "method,target,actor",
    [("decline", ShareStatus.DECLINED, "bob"), ("cancel", ShareStatus.CANCELED, "alice")],
)
async def test_decisions_are_role_scoped_and_idempotent(repository, method, target, actor):
    repository.get.return_value = invitation()
    repository.transition.return_value = True
    service = ShareNotifications(repository)
    decide = getattr(service, method)
    await decide("invite", Identity.user(actor))
    repository.transition.assert_awaited_once_with("invite", target, ANY)
    repository.get.return_value = invitation(status=target)
    await decide("invite", Identity.user(actor))
    repository.transition.assert_awaited_once()
    with pytest.raises(PermissionError):
        await decide("invite", Identity.user("mallory"))


async def test_racing_decisions_return_success_only_for_the_same_outcome(repository):
    service = ShareNotifications(repository)
    repository.transition.return_value = False
    for outcome in (ShareStatus.DECLINED, ShareStatus.CANCELED, ShareStatus.ACCEPTED):
        repository.get.side_effect = [invitation(), invitation(status=outcome)]
        if outcome == ShareStatus.DECLINED:
            await service.decline("invite", Identity.user("bob"))
        else:
            with pytest.raises(ShareConflict, match="no longer pending"):
                await service.decline("invite", Identity.user("bob"))


async def test_query_cancellation_reaches_the_repository(repository):
    entered, released = asyncio.Event(), asyncio.Event()

    async def waiting(*arguments):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    repository.list.side_effect = waiting
    task = asyncio.create_task(ShareNotifications(repository).list(Identity.user("bob")))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()
