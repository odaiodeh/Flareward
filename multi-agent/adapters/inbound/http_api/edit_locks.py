"""Existing team-editor endpoints use authenticated actors and application leases."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from mas.application.collaboration.editing import EditEntityKind, EditLease, TeamEditService
from mas.core.identity import Identity
from pydantic import BaseModel, ConfigDict, Field

from inbound.http_api.dependencies import authenticated, get_team_editing

router = APIRouter(prefix="/api/collaboration", tags=["team editing"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[TeamEditService, Depends(get_team_editing)]


class LockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    team_id: str = Field(alias="teamId", min_length=1)
    entity_kind: EditEntityKind = Field(alias="entityKind")
    entity_id: str = Field(alias="entityId", min_length=1)
    lease_id: str | None = Field(default=None, alias="leaseId", min_length=1, max_length=128)
    # Accepted for existing clients; authentication is authoritative for the actor/display name.
    user_id: str | None = Field(default=None, alias="userId")
    display_name: str | None = Field(default=None, alias="displayName")


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str = Field(alias="teamId", min_length=1)
    entity_kind: EditEntityKind = Field(alias="entityKind")
    entity_ids: tuple[str, ...] = Field(alias="entityIds", max_length=500)


class Holder(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    user_id: str = Field(alias="userId")
    display_name: str = Field(alias="displayName")


class Acquisition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    acquired: bool
    locked_by: Holder | None = Field(default=None, alias="lockedBy")


class Renewal(BaseModel):
    renewed: bool


class Released(BaseModel):
    success: bool = True


class Statuses(BaseModel):
    locks: dict[str, Holder | None]


class Status(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    locked: bool
    locked_by: Holder | None = Field(default=None, alias="lockedBy")


def holder_view(lease: EditLease | None) -> Holder | None:
    return Holder(user_id=lease.user_id, display_name=lease.display_name) if lease else None


def actor_lease(request: Request, body: LockRequest) -> EditLease:
    user_id = request.state.authenticated_user
    return EditLease(user_id=user_id, display_name=user_id, lease_id=body.lease_id)


@router.post("/edit_lock.acquire", response_model=Acquisition)
async def acquire(
    body: LockRequest, request: Request, caller: Caller, service: Service
) -> Acquisition:
    holder = await service.acquire(
        caller, body.entity_kind, body.entity_id, actor_lease(request, body)
    )
    return Acquisition(acquired=holder is None, locked_by=holder_view(holder))


@router.post("/edit_lock.release", response_model=Released)
async def release(
    body: LockRequest, request: Request, caller: Caller, service: Service
) -> Released:
    await service.release(caller, body.entity_kind, body.entity_id, actor_lease(request, body))
    return Released()


@router.post("/edit_lock.heartbeat", response_model=Renewal)
async def heartbeat(
    body: LockRequest, request: Request, caller: Caller, service: Service
) -> Renewal:
    return Renewal(
        renewed=await service.renew(
            caller, body.entity_kind, body.entity_id, actor_lease(request, body)
        )
    )


@router.post("/edit_lock.statuses", response_model=Statuses)
async def statuses(body: StatusRequest, caller: Caller, service: Service) -> Statuses:
    holders = await service.holders(caller, body.entity_kind, body.entity_ids)
    return Statuses(locks={entity_id: holder_view(holder) for entity_id, holder in holders.items()})


@router.get("/edit_lock.status", response_model=Status)
async def status(
    caller: Caller,
    service: Service,
    team_id: Annotated[str, Query(alias="teamId", min_length=1)],
    entity_kind: Annotated[EditEntityKind, Query(alias="entityKind")],
    entity_id: Annotated[str, Query(alias="entityId", min_length=1)],
) -> Status:
    holders = await service.holders(caller, entity_kind, (entity_id,))
    holder = holders.get(entity_id)
    return Status(locked=holder is not None, locked_by=holder_view(holder))
