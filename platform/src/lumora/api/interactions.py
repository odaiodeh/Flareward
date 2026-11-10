"""Thin native streaming and approval endpoints, scoped through execution ownership."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import JsonValue

from lumora.api.dependencies import authenticated, get_interactions
from lumora.services.identity.domain import Identity
from lumora.services.interactions.models import (
    ApprovalRulesUpdate,
    ApprovalSubmission,
    ApprovalTicket,
    StreamCursorExpired,
)
from lumora.services.interactions.service import InteractionService

router = APIRouter(prefix="/api/executions", tags=["interactions"])
type Interactions = Annotated[InteractionService, Depends(get_interactions)]
type Caller = Annotated[Identity, Depends(authenticated)]


@router.get("/{execution_id}/approvals", response_model=list[ApprovalTicket])
async def pending(execution_id: str, caller: Caller, interactions: Interactions):
    return await interactions.pending(execution_id, caller)


@router.post("/{execution_id}/approvals/{request_id}", status_code=202)
async def respond(
    execution_id: str,
    request_id: str,
    submission: ApprovalSubmission,
    caller: Caller,
    interactions: Interactions,
) -> dict[str, str]:
    await interactions.respond(execution_id, request_id, submission, caller)
    return {"status": "accepted"}


@router.get("/{execution_id}/approval-rules")
async def rules(
    execution_id: str, caller: Caller, interactions: Interactions
) -> dict[str, JsonValue]:
    return (await interactions.rules(execution_id, caller)).to_dict()


@router.put("/{execution_id}/approval-rules")
async def update_rules(
    execution_id: str,
    update: ApprovalRulesUpdate,
    caller: Caller,
    interactions: Interactions,
) -> dict[str, JsonValue]:
    return (await interactions.update_rules(execution_id, update, caller)).to_dict()


@router.get("/{execution_id}/stream")
async def stream(
    execution_id: str,
    caller: Caller,
    interactions: Interactions,
    after: Annotated[str, Query(pattern=r"^[0-9]{1,20}-[0-9]{1,20}$")] = "0-0",
) -> StreamingResponse:
    await interactions.validate_stream(execution_id, caller, after)

    async def events() -> AsyncIterator[str]:
        try:
            async for event in interactions.events(execution_id, caller, after=after):
                if event is None:
                    yield ": heartbeat\n\n"
                else:
                    yield f"id: {event.cursor}\ndata: {event.model_dump_json()}\n\n"
        except StreamCursorExpired:
            yield 'event: error\ndata: {"code":"stream_cursor_expired"}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream")
