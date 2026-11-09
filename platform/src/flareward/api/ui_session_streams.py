"""Translate application execution events to the existing UI's session NDJSON transport."""

import json
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, JsonValue

from flareward.api.dependencies import (
    HttpServices,
    authenticated,
    get_interactions,
    get_services,
    get_sessions,
)
from flareward.api.ui_sessions import SessionSelection
from flareward.executions.domain.models import TERMINAL_PHASES, ExecutionPhase
from flareward.services.identity.domain import Identity
from flareward.services.interactions.models import (
    ApprovalRulesUpdate,
    ApprovalSubmission,
    StreamCursorExpired,
)
from flareward.services.interactions.rules import ApprovalRuleChange
from flareward.services.interactions.service import InteractionService
from flareward.services.interactions.tools.models import ApprovalDecision
from flareward.services.sessions.execution.program_sessions import ProgramSessionService

router = APIRouter(prefix="/api/sessions", tags=["chat interactions"], include_in_schema=False)
type Caller = Annotated[Identity, Depends(authenticated)]
type Sessions = Annotated[ProgramSessionService, Depends(get_sessions)]
type Interactions = Annotated[InteractionService, Depends(get_interactions)]
type SessionId = Annotated[str, Query(alias="sessionId", min_length=1)]


class StreamStatus(StrEnum):
    UNKNOWN = "unknown"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatStreamStatus(BaseModel):
    session_id: str
    execution_id: str
    status: StreamStatus
    is_active: bool
    # The native stream has no count/timing monitor. Unknown metadata stays null.
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    error: str | None = None
    event_count: int | None = None
    last_event_id: str | None = None


class ChatApproval(SessionSelection, ApprovalSubmission):
    execution_id: str = Field(alias="executionId", min_length=1)
    request_id: str = Field(alias="requestId", min_length=1)
    modified_args: dict[str, JsonValue] = Field(default_factory=dict, alias="modifiedArgs")


class ChatRuleChange(SessionSelection, ApprovalRuleChange):
    execution_id: str = Field(alias="executionId", min_length=1)
    node_uid: str | None = Field(default=None, alias="nodeUid", min_length=1)
    tool_name: str | None = Field(default=None, alias="toolName", min_length=1)


class ChatRules(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    overrides: ApprovalRulesUpdate


class SavedChatRules(ChatRules):
    status: Literal["saved"] = "saved"


class SubmittedApproval(BaseModel):
    status: Literal["submitted"] = "submitted"
    session_id: str = Field(serialization_alias="sessionId")
    execution_id: str = Field(serialization_alias="executionId")
    request_id: str = Field(serialization_alias="requestId")
    decision: ApprovalDecision


@router.get("/session.stream.status", response_model=ChatStreamStatus)
async def stream_status(
    session_id: SessionId, caller: Caller, sessions: Sessions
) -> ChatStreamStatus:
    execution = await sessions.active_execution(session_id, caller)
    active = execution.phase not in TERMINAL_PHASES
    status = (
        StreamStatus.UNKNOWN
        if execution.phase in {ExecutionPhase.SUBMITTING, ExecutionPhase.UNKNOWN}
        else StreamStatus.RUNNING
        if active
        else StreamStatus(execution.phase.value)
    )
    return ChatStreamStatus(
        session_id=session_id,
        execution_id=execution.execution_id,
        status=status,
        is_active=active,
        error=execution.failure.message if execution.failure else None,
    )


@router.get("/session.subscribe")
async def subscribe(
    session_id: SessionId,
    caller: Caller,
    sessions: Sessions,
    interactions: Interactions,
    services: Annotated[HttpServices, Depends(get_services)],
    execution_id: Annotated[str | None, Query(alias="executionId", min_length=1)] = None,
    after: Annotated[str, Query(pattern=r"^[0-9]{1,20}-[0-9]{1,20}$")] = "0-0",
) -> StreamingResponse:
    execution = await sessions.active_execution(session_id, caller, expected_id=execution_id)
    pinned_id = execution.execution_id
    await interactions.validate_stream(pinned_id, caller, after)

    async def events() -> AsyncIterator[str]:
        try:
            async for event in interactions.events(pinned_id, caller, after=after):
                data = (
                    {"type": "heartbeat"}
                    if event is None
                    else {
                        **event.data,
                        "cursor": event.cursor,
                        "execution_id": event.execution_id,
                        "root_execution_id": pinned_id,
                    }
                )
                yield json.dumps(data) + "\n"
            final = await services.executions.refresh(pinned_id, caller)
            if final.phase == ExecutionPhase.FAILED:
                yield (
                    json.dumps(
                        {
                            "type": "stream_error",
                            "error": final.failure.message if final.failure else "Execution failed",
                        }
                    )
                    + "\n"
                )
            else:
                yield (
                    json.dumps(
                        {
                            "type": "stream_end",
                            "status": final.phase.value,
                            "execution_id": pinned_id,
                        }
                    )
                    + "\n"
                )
        except StreamCursorExpired:
            yield (
                json.dumps(
                    {
                        "type": "stream_error",
                        "error": "Stream history expired; reload session state",
                    }
                )
                + "\n"
            )

    return StreamingResponse(
        events(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"}
    )


@router.post("/session.approval", response_model=SubmittedApproval)
async def respond(
    body: ChatApproval, caller: Caller, sessions: Sessions, interactions: Interactions
) -> SubmittedApproval:
    execution = await sessions.active_execution(
        body.session_id, caller, expected_id=body.execution_id
    )
    await interactions.respond(
        execution.execution_id,
        body.request_id,
        ApprovalSubmission(
            decision=body.decision, feedback=body.feedback, modified_args=body.modified_args
        ),
        caller,
    )
    return SubmittedApproval(
        session_id=body.session_id,
        execution_id=execution.execution_id,
        request_id=body.request_id,
        decision=body.decision,
    )


@router.get("/session.approval.rules", response_model=ChatRules)
async def rules(session_id: SessionId, caller: Caller, sessions: Sessions) -> ChatRules:
    return ChatRules(
        session_id=session_id,
        overrides=ApprovalRulesUpdate.model_validate(
            (await sessions.approval_rules(session_id, caller)).to_dict()
        ),
    )


@router.post(
    "/session.approval.rule",
    response_model=SavedChatRules,
    dependencies=[Depends(get_interactions)],
)
async def change_rule(body: ChatRuleChange, caller: Caller, sessions: Sessions) -> SavedChatRules:
    updated = await sessions.change_approval_rule(
        body.session_id,
        body.execution_id,
        ApprovalRuleChange(action=body.action, node_uid=body.node_uid, tool_name=body.tool_name),
        caller,
    )
    return SavedChatRules(
        session_id=body.session_id, overrides=ApprovalRulesUpdate.model_validate(updated.to_dict())
    )
