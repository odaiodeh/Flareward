"""Existing notification transports delegate ownership and decisions to application policy."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from mas.application.sharing.notifications import ShareNotifications
from mas.core.identity import Identity
from mas.domain.sharing import ShareDirection, ShareInvite, ShareItemKind, ShareStatus
from pydantic import BaseModel, ConfigDict, Field

from inbound.http_api.dependencies import authenticated, get_share_notifications

router = APIRouter(prefix="/api/shares", tags=["sharing notifications"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ShareNotifications, Depends(get_share_notifications)]


class InvitationView(BaseModel):
    share_id: str
    sender_identity: Identity
    recipient_identity: Identity
    sender_user_id: str
    sender_display_name: str
    recipient_user_id: str
    recipient_display_name: str
    item_kind: ShareItemKind
    item_id: str
    item_name: str
    message: str | None
    status: ShareStatus
    created_at: datetime
    expires_at: datetime
    ttl_days: int
    is_expired: bool
    accepted_at: datetime | None
    declined_at: datetime | None
    result_mapping: dict[str, str]

    @classmethod
    def from_invite(cls, invite: ShareInvite) -> InvitationView:
        return cls.model_validate(
            {
                **invite.model_dump(),
                "sender_user_id": invite.sender_identity.id,
                "sender_display_name": invite.sender_identity.display_name,
                "recipient_user_id": invite.recipient_identity.id,
                "recipient_display_name": invite.recipient_identity.display_name,
            }
        )


class InvitationList(BaseModel):
    invites: list[InvitationView]
    count: int


class InvitationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    share_id: str = Field(min_length=1, alias="shareId")
    team_id: str | None = Field(default=None, alias="teamId")


class DecisionResult(BaseModel):
    status: Literal["success"] = "success"


@router.get("/shares.list")
async def list_invitations(
    caller: Caller,
    service: Service,
    direction: ShareDirection = ShareDirection.RECEIVED,
    status: ShareStatus | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> InvitationList:
    invites = await service.list(
        caller, direction=direction, status=status, offset=skip, limit=limit
    )
    return InvitationList(
        invites=[InvitationView.from_invite(invite) for invite in invites], count=len(invites)
    )


@router.get("/share.get")
async def get_invitation(
    caller: Caller, service: Service, share_id: Annotated[str, Query(min_length=1, alias="shareId")]
) -> InvitationView:
    return InvitationView.from_invite(await service.get(share_id, caller))


@router.post("/share.decline")
async def decline_invitation(
    body: InvitationDecision, caller: Caller, service: Service
) -> DecisionResult:
    await service.decline(body.share_id, caller)
    return DecisionResult()


@router.post("/share.cancel")
async def cancel_invitation(
    body: InvitationDecision, caller: Caller, service: Service
) -> DecisionResult:
    await service.cancel(body.share_id, caller)
    return DecisionResult()
