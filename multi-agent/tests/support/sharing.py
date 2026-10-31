"""Application-only invitation scenarios and shared repository behavior."""

from datetime import UTC, datetime, timedelta

from mas.core.identity import Identity
from mas.domain.sharing import ShareInvite, ShareItemKind, ShareStatus


def invitation(share_id: str = "invite", **changes) -> ShareInvite:
    return ShareInvite.model_validate(
        {
            "share_id": share_id,
            "sender_identity": Identity.user("alice"),
            "recipient_identity": Identity.user("bob"),
            "item_kind": ShareItemKind.RESOURCE,
            "item_id": "resource",
            "item_name": "Shared resource",
            "created_at": datetime.now(UTC),
            "authorized_owner_ids": ["alice", "internal-owner-pool"],
            **changes,
        }
    )


def repository_invitations() -> list[ShareInvite]:
    at = datetime.now(UTC) - timedelta(days=1)
    return [
        invitation("a", created_at=at),
        invitation("b", created_at=at),
        invitation("latest", created_at=at + timedelta(hours=1)),
        invitation("other", recipient_identity=Identity.user("other")),
        invitation("team", recipient_identity=Identity.team("bob")),
        invitation("closed", status=ShareStatus.ACCEPTED),
    ]
