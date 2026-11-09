"""In-process storage follows the shared invitation contract without caller-owned state."""

from support.share_notification_contracts import verify_notification_repository
from support.sharing import repository_invitations

from flareward.services.sharing.adapters.memory.share_notifications import MemoryShareNotifications


async def test_memory_notification_snapshots_and_atomic_decisions():
    invites = repository_invitations()
    repository = MemoryShareNotifications(invites)
    invites[0].item_name = "changed"
    assert (await repository.get("a")).item_name == "Shared resource"
    await verify_notification_repository(repository)
