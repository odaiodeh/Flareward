"""Existing chat HTTP shapes backed by native program sessions and application queries."""

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from flareward.api.dependencies import (
    authenticated,
    get_blueprint_sessions,
    get_session_queries,
    get_sessions,
)
from flareward.programs.graph.state.graph_state import GraphState
from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.dto import PaginatedSessions, SessionListFilter
from flareward.services.sessions.domain.models import SessionChat, SessionMeta
from flareward.services.sessions.domain.status import SessionStatus
from flareward.services.sessions.execution.blueprint_sessions import BlueprintSessionService
from flareward.services.sessions.execution.program_sessions import (
    ProgramSessionService,
    StartSessionTurn,
)
from flareward.services.sessions.execution.projection import SessionProjection
from flareward.services.sessions.execution.queries import SessionQueryService

router = APIRouter(prefix="/api/sessions", tags=["chat sessions"], include_in_schema=False)
type Caller = Annotated[Identity, Depends(authenticated)]
type Sessions = Annotated[ProgramSessionService, Depends(get_sessions)]
type Blueprints = Annotated[BlueprintSessionService, Depends(get_blueprint_sessions)]
type Queries = Annotated[SessionQueryService, Depends(get_session_queries)]
type SessionId = Annotated[str, Query(alias="sessionId", min_length=1)]


class ChatScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: str | None = Field(default=None, alias="teamId")


class CreateChat(ChatScope):
    blueprint_id: str = Field(alias="blueprintId", min_length=1)
    metadata: SessionMeta = Field(default_factory=SessionMeta)
    hitl_enabled: bool = Field(default=False, alias="hitlEnabled")


class SessionSelection(ChatScope):
    session_id: str = Field(alias="sessionId", min_length=1)


class SubmitChat(SessionSelection):
    inputs: dict[str, JsonValue]
    execution_id: str = Field(
        default_factory=lambda: str(uuid4()), alias="executionId", min_length=1
    )
    scope: Literal["public", "private"] = "public"


class SubmittedChat(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    execution_id: str = Field(serialization_alias="executionId")


class ChatCancellation(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    status: SessionStatus


class ChatMetadata(SessionSelection):
    meta: SessionMeta


class ChatMetadataResponse(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    meta: SessionMeta


@router.post("/user.session.create", response_model=str)
async def create_chat(body: CreateChat, caller: Caller, blueprints: Blueprints) -> str:
    metadata = body.metadata
    if "hitl_enabled" not in metadata.model_fields_set:
        metadata = metadata.model_copy(update={"hitl_enabled": body.hitl_enabled})
    return (await blueprints.create(body.blueprint_id, caller, metadata=metadata)).run_id


@router.post("/user.session.submit", response_model=SubmittedChat, status_code=202)
async def submit_chat(
    body: SubmitChat, request: Request, caller: Caller, sessions: Sessions
) -> SubmittedChat:
    record = await sessions.start(
        body.session_id,
        StartSessionTurn(inputs=body.inputs, execution_id=body.execution_id, scope=body.scope),
        caller,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
    )
    return SubmittedChat(session_id=record.run_id, execution_id=body.execution_id)


@router.get("/session.chat.get", response_model=SessionChat)
async def chat(session_id: SessionId, caller: Caller, queries: Queries) -> SessionChat:
    return await queries.chat(session_id, caller)


@router.get("/session.state.get", response_model=GraphState)
async def state(session_id: SessionId, caller: Caller, sessions: Sessions) -> GraphState:
    return SessionProjection.conversation(await sessions.refresh(session_id, caller))


@router.get("/session.status.get", response_model=SessionStatus)
async def status(session_id: SessionId, caller: Caller, sessions: Sessions) -> SessionStatus:
    return (await sessions.refresh(session_id, caller)).status


@router.post("/session.cancel", response_model=ChatCancellation, status_code=202)
async def cancel(body: SessionSelection, caller: Caller, sessions: Sessions) -> ChatCancellation:
    record = await sessions.cancel(body.session_id, caller)
    return ChatCancellation(session_id=record.run_id, status=record.status)


@router.get("/session.user.list", response_model=PaginatedSessions)
async def list_chats(
    caller: Caller,
    queries: Queries,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    filters: str | None = None,
) -> PaginatedSessions:
    try:
        selection = (
            SessionListFilter.model_validate_json(filters) if filters else SessionListFilter()
        )
    except ValidationError:
        raise ValueError("Invalid session filters") from None
    return await queries.list(caller, selection, offset=offset, limit=limit)


@router.delete("/session.delete")
async def delete(session_id: SessionId, caller: Caller, sessions: Sessions) -> dict[str, bool]:
    await sessions.delete(session_id, caller)
    return {"success": True}


@router.get("/session.meta", response_model=ChatMetadataResponse)
async def metadata(
    session_id: SessionId, caller: Caller, sessions: Sessions
) -> ChatMetadataResponse:
    return ChatMetadataResponse(
        session_id=session_id, meta=(await sessions.get(session_id, caller)).metadata
    )


@router.post("/session.meta", response_model=ChatMetadataResponse)
async def update_metadata(
    body: ChatMetadata, caller: Caller, sessions: Sessions
) -> ChatMetadataResponse:
    record = await sessions.update_metadata(body.session_id, body.meta, caller)
    return ChatMetadataResponse(session_id=record.run_id, meta=record.metadata)
