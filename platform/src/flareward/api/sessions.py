"""Session HTTP contracts; orchestration and ownership live in application services."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from flareward.api.dependencies import authenticated, get_services, get_sessions, human_principal
from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.models import SessionMeta
from flareward.services.sessions.execution.program_sessions import (
    CreateProgramSession,
    ProgramSessionService,
    StartSessionTurn,
)
from flareward.services.sessions.records import SessionRecord

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
type Sessions = Annotated[ProgramSessionService, Depends(get_sessions)]
type Caller = Annotated[Identity, Depends(authenticated)]


@router.post("", response_model=SessionRecord, status_code=201)
async def create_session(
    request: CreateProgramSession, caller: Caller, sessions: Sessions
) -> SessionRecord:
    return await sessions.create(request, caller)


@router.get("", response_model=list[SessionRecord])
async def list_sessions(
    caller: Caller,
    sessions: Sessions,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[SessionRecord]:
    return await sessions.list(caller, limit=limit)


@router.get("/{session_id}", response_model=SessionRecord)
async def get_session(session_id: str, caller: Caller, sessions: Sessions) -> SessionRecord:
    return await sessions.refresh(session_id, caller)


@router.post("/{session_id}/executions", response_model=SessionRecord, status_code=202)
async def start_turn(
    session_id: str,
    request: StartSessionTurn,
    http_request: Request,
    caller: Caller,
    sessions: Sessions,
) -> SessionRecord:
    approved_by = None
    if request.workflow_access:
        principal = await human_principal(http_request, get_services(http_request))
        if not principal.owner.owns(caller):
            raise PermissionError("Workflow access owner differs from the authenticated owner")
        approved_by = principal.user
    return await sessions.start(
        session_id,
        request,
        caller,
        credential_user_id=getattr(http_request.state, "authenticated_user", ""),
        approved_by=approved_by,
    )


@router.post("/{session_id}/cancel", response_model=SessionRecord, status_code=202)
async def cancel_session(session_id: str, caller: Caller, sessions: Sessions) -> SessionRecord:
    return await sessions.cancel(session_id, caller)


@router.put("/{session_id}/metadata", response_model=SessionRecord)
async def update_metadata(
    session_id: str,
    metadata: SessionMeta,
    caller: Caller,
    sessions: Sessions,
) -> SessionRecord:
    return await sessions.update_metadata(session_id, metadata, caller)
