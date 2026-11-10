"""Sharing values and identity rules, independent of cloning and infrastructure."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, field_validator

from lumora.services.identity.domain import Identity, IdentityType


class ShareStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELED = "canceled"


class ShareItemKind(StrEnum):
    RESOURCE = "resource"
    BLUEPRINT = "blueprint"


class ShareDirection(StrEnum):
    RECEIVED = "received"
    SENT = "sent"


def matches_share_identity(identity: Identity, caller: Identity) -> bool:
    if identity.type != caller.type:
        return False
    return (
        identity.id.casefold() == caller.id.casefold()
        if identity.type == IdentityType.USER
        else identity.id == caller.id
    )


class ShareInvite(BaseModel):
    share_id: str = Field(default_factory=lambda: str(uuid4()))
    sender_identity: Identity
    recipient_identity: Identity
    item_kind: ShareItemKind
    item_id: str
    item_name: str
    message: str | None = None
    status: ShareStatus = ShareStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accepted_at: datetime | None = None
    declined_at: datetime | None = None
    ttl_days: int = 10
    expires_at: datetime = Field(
        default_factory=lambda data: data["created_at"] + timedelta(days=data["ttl_days"])
    )
    authorized_owner_ids: list[str] = Field(default_factory=list)
    result_mapping: dict[str, str] = Field(default_factory=dict)

    def participant(self, direction: ShareDirection) -> Identity:
        return (
            self.recipient_identity
            if direction == ShareDirection.RECEIVED
            else self.sender_identity
        )

    @field_validator("created_at", "expires_at", "accepted_at", "declined_at")
    @classmethod
    def utc_dates(cls, value: datetime | None) -> datetime | None:
        # Old Mongo clients decode BSON timestamps without tzinfo; strings are also retained.
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at


class ShareResult(BaseModel):
    share_id: str
    new_item_id: str
    rid_mapping: dict[str, str] = Field(default_factory=dict)
    created_resources: int = 0
    name_conflicts: dict[str, str] = Field(default_factory=dict)
