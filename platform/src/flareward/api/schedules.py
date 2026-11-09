"""Authenticated calendar operations delegate to application services."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import Field

from flareward.api.dependencies import (
    HumanPrincipal,
    authenticated,
    get_schedules,
    get_services,
    get_sessions,
    human_principal,
)
from flareward.models import Model
from flareward.services.identity.domain import Identity
from flareward.services.scheduling.programs import (
    CreateProgramSchedule,
    ProgramScheduleService,
    ProgramScheduleView,
)
from flareward.services.sessions.execution.program_sessions import ProgramSessionService
from flareward.services.sessions.records import SessionRecord

router = APIRouter(prefix="/api/program-schedules", tags=["program schedules"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ProgramScheduleService, Depends(get_schedules)]


class UpdateProgramSchedule(Model):
    request: CreateProgramSchedule
    expected_version: int = Field(ge=1)


@router.post("", response_model=ProgramScheduleView, status_code=201)
async def create(
    body: CreateProgramSchedule,
    caller: Caller,
    service: Service,
    request: Request,
    request_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=256)
    ] = None,
) -> ProgramScheduleView:
    approved_by = None
    if body.workflow_access is not None:
        principal = await human_principal(request, get_services(request))
        if not principal.owner.owns(caller):
            raise PermissionError("Schedule consent owner differs from its authenticated owner")
        approved_by = principal.user
    return await service.create(
        body,
        caller,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        request_key=request_key,
        approved_by=approved_by,
    )


@router.get("", response_model=list[ProgramScheduleView])
async def list_schedules(
    caller: Caller, service: Service, limit: Annotated[int, Query(ge=1, le=100)] = 100
) -> list[ProgramScheduleView]:
    return await service.list(caller, limit=limit)


@router.get("/{schedule_id}", response_model=ProgramScheduleView)
async def get(schedule_id: str, caller: Caller, service: Service) -> ProgramScheduleView:
    return await service.get(schedule_id, caller)


@router.put("/{schedule_id}", response_model=ProgramScheduleView)
async def update(
    schedule_id: str,
    body: UpdateProgramSchedule,
    caller: Caller,
    service: Service,
    request: Request,
) -> ProgramScheduleView:
    approved_by = None
    if body.request.workflow_access is not None:
        principal = await human_principal(request, get_services(request))
        if not principal.owner.owns(caller):
            raise PermissionError("Schedule consent owner differs from its authenticated owner")
        approved_by = principal.user
    return await service.update(
        schedule_id,
        body.request,
        caller,
        expected_version=body.expected_version,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        approved_by=approved_by,
    )


@router.post("/{schedule_id}/pause", response_model=ProgramScheduleView)
async def pause(schedule_id: str, caller: Caller, service: Service) -> ProgramScheduleView:
    return await service.pause(schedule_id, caller, paused=True)


@router.post("/{schedule_id}/resume", response_model=ProgramScheduleView)
async def resume(schedule_id: str, caller: Caller, service: Service) -> ProgramScheduleView:
    return await service.pause(schedule_id, caller, paused=False)


@router.post("/{schedule_id}/trigger", response_model=ProgramScheduleView, status_code=202)
async def trigger(schedule_id: str, caller: Caller, service: Service) -> ProgramScheduleView:
    return await service.trigger(schedule_id, caller)


@router.delete("/{schedule_id}", status_code=204)
async def delete(schedule_id: str, caller: Caller, service: Service) -> Response:
    await service.delete(schedule_id, caller)
    return Response(status_code=204)


@router.delete("/{schedule_id}/workflow-access", status_code=204)
async def revoke_workflow_access(
    schedule_id: str,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    service: Service,
) -> Response:
    await service.revoke_workflow_access(schedule_id, principal.owner)
    return Response(status_code=204)


@router.get("/{schedule_id}/runs", response_model=list[SessionRecord])
async def runs(
    schedule_id: str,
    caller: Caller,
    service: Service,
    sessions: Annotated[ProgramSessionService, Depends(get_sessions)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SessionRecord]:
    await service.get(schedule_id, caller)
    return list(await sessions.scheduled(schedule_id, caller, limit=limit))
