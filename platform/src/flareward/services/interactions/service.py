"""Authorize interactions against application execution ownership before transport access."""

from collections.abc import AsyncIterator

from flareward.executions.domain.models import TERMINAL_PHASES
from flareward.executions.service import ExecutionService
from flareward.services.identity.domain import Identity
from flareward.services.interactions.models import (
    ApprovalRulesUpdate,
    ApprovalSubmission,
    ApprovalTicket,
    StreamEvent,
    initial_rules,
)
from flareward.services.interactions.ports import InteractionStore
from flareward.services.interactions.tools.models import ApprovalOverrides


class InteractionService:
    def __init__(self, executions: ExecutionService, store: InteractionStore) -> None:
        self._executions = executions
        self._store = store

    async def _root(self, execution_id: str, caller: Identity) -> str:
        record = await self._executions.get(execution_id, caller)
        return record.context.root_execution_id or record.execution_id

    async def pending(self, execution_id: str, caller: Identity) -> list[ApprovalTicket]:
        return await self._store.pending(await self._root(execution_id, caller))

    async def respond(
        self,
        execution_id: str,
        request_id: str,
        submission: ApprovalSubmission,
        caller: Identity,
    ) -> None:
        record = await self._executions.get(execution_id, caller)
        await self._store.respond(
            record.context.root_execution_id or record.execution_id,
            submission.response(request_id),
            allow_pending=record.phase not in TERMINAL_PHASES,
        )

    async def rules(self, execution_id: str, caller: Identity) -> ApprovalOverrides:
        record = await self._executions.get(execution_id, caller)
        rules = await self._store.load_rules(
            record.context.root_execution_id or record.execution_id
        )
        return rules if rules is not None else initial_rules(record.context)

    async def update_rules(
        self,
        execution_id: str,
        rules: ApprovalRulesUpdate,
        caller: Identity,
    ) -> ApprovalOverrides:
        root = await self._root(execution_id, caller)
        domain = rules.domain()
        await self._store.save_rules(root, domain)
        return domain

    async def events(
        self,
        execution_id: str,
        caller: Identity,
        *,
        after: str = "0-0",
    ) -> AsyncIterator[StreamEvent | None]:
        root = await self._root(execution_id, caller)
        while True:
            events = await self._store.read(root, after)
            for event in events:
                after = event.cursor
                yield event
            if not events:
                record = await self._executions.refresh(execution_id, caller)
                if record.phase in TERMINAL_PHASES:
                    return
                yield None

    async def validate_stream(self, execution_id: str, caller: Identity, after: str) -> None:
        await self._store.read(await self._root(execution_id, caller), after, block_ms=0)
