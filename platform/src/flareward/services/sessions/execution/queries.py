"""Authorized chat/list projections remain independent of HTTP and storage adapters."""

from flareward.programs.templates.authoring import BlueprintAuthoringService
from flareward.programs.templates.contracts import BlueprintDocument
from flareward.services.identity.domain import Identity
from flareward.services.sessions.domain.dto import (
    PaginatedSessions,
    PaginationMeta,
    SessionListFilter,
    SessionListItem,
)
from flareward.services.sessions.domain.models import SessionChat
from flareward.services.sessions.execution.program_sessions import ProgramSessionService
from flareward.services.sessions.execution.projection import SessionProjection
from flareward.services.sessions.records import SessionRecord


class SessionQueryService:
    def __init__(
        self, sessions: ProgramSessionService, blueprints: BlueprintAuthoringService | None
    ) -> None:
        self._sessions, self._blueprints = sessions, blueprints

    async def _blueprint(self, record: SessionRecord, caller: Identity) -> BlueprintDocument | None:
        if self._blueprints is None or not record.blueprint_id:
            return None
        try:
            return await self._blueprints.get(record.blueprint_id, caller)
        except KeyError, PermissionError:
            return None

    async def chat(self, session_id: str, caller: Identity) -> SessionChat:
        record = await self._sessions.refresh(session_id, caller)
        state = SessionProjection.conversation(record)
        return SessionChat(
            messages=state.messages,
            output=state.output,
            status=record.status.value,
            status_message=record.metadata.status_message,
            blueprint_id=record.blueprint_id,
            blueprint_exists=await self._blueprint(record, caller) is not None,
        )

    async def list(
        self, caller: Identity, filters: SessionListFilter, *, offset: int = 0, limit: int = 50
    ) -> PaginatedSessions:
        page = await self._sessions.query(caller, filters, offset=offset, limit=limit)
        blueprints: dict[str, BlueprintDocument | None] = {}
        items = []
        for record in page.records:
            if record.blueprint_id not in blueprints:
                blueprints[record.blueprint_id] = await self._blueprint(record, caller)
            blueprint = blueprints[record.blueprint_id]
            items.append(
                SessionListItem.from_doc(
                    record.model_dump(mode="json"),
                    blueprint_exists=blueprint is not None,
                    public_usage_scope=blueprint is not None
                    and blueprint.metadata.get("usageScope") == "public",
                    blueprint_metadata=blueprint.metadata if blueprint is not None else {},
                )
            )
        return PaginatedSessions(
            sessions=items,
            pagination=PaginationMeta(
                total=page.total,
                offset=page.offset,
                limit=page.limit,
                has_more=page.offset + len(items) < page.total,
            ),
        )
