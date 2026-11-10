"""Async application interaction persistence; no transport objects cross this boundary."""

from typing import Protocol

from lumora.services.interactions.models import ApprovalTicket, StreamEvent
from lumora.services.interactions.tools.models import ApprovalOverrides, ApprovalResponse


class ApprovalRulesPublisher(Protocol):
    async def save_rules(
        self, root_id: str, rules: ApprovalOverrides, *, revision: int | None = None
    ) -> None: ...


class InteractionStore(ApprovalRulesPublisher, Protocol):
    async def read(self, root_id: str, after: str, *, block_ms: int = 500) -> list[StreamEvent]: ...
    async def pending(self, root_id: str) -> list[ApprovalTicket]: ...
    async def respond(
        self,
        root_id: str,
        response: ApprovalResponse,
        *,
        allow_pending: bool = True,
    ) -> None: ...
    async def load_rules(self, root_id: str) -> ApprovalOverrides | None: ...
    async def cancel(self, execution_id: str, *, root_execution_id: str | None = None) -> None: ...
