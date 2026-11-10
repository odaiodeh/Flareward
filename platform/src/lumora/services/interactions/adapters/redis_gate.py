"""Async approval transport with atomic decisions and owned pending tickets."""

import asyncio
import json

from redis.asyncio import Redis

from lumora.async_work import await_owned
from lumora.executions.domain.context import ExecutionContext
from lumora.services.interactions.adapters.errors import redis_async
from lumora.services.interactions.adapters.wire import (
    CHECK_CANCELLED,
    CLOSE_PENDING,
    CREATE,
    POLL,
    approval_event,
    canonical,
    request_key,
    response_result,
    root_key,
)
from lumora.services.interactions.models import REQUEST, RESPONSE, ApprovalStatus
from lumora.services.interactions.tools.models import (
    ApprovalDecision,
    ApprovalOverrides,
    ApprovalRequest,
    ApprovalResponse,
    HITLConfig,
)
from lumora.services.interactions.tools.ports import ApprovalGate


class RedisApprovalGate(ApprovalGate):
    def __init__(
        self,
        client: Redis,
        context: ExecutionContext,
        cancelled: asyncio.Event,
        config: HITLConfig,
        *,
        ttl: int = 86400,
        max_events: int = 10000,
    ) -> None:
        super().__init__(config)
        self._client, self._context, self._cancelled = client, context, cancelled
        self._ttl, self._max_events = ttl, max_events
        self._scope = canonical(
            list(dict.fromkeys((*context.ancestor_execution_ids, context.execution_id)))
        )

    @redis_async
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        base = root_key(self._context.root_execution_id)
        if self._cancelled.is_set() or await self._client.eval(
            CHECK_CANCELLED, 1, base + ":cancelled", self._scope
        ):
            return self._rejected(request)
        raw = await self._client.get(base + ":rules")
        rules = ApprovalOverrides.from_dict(json.loads(raw)) if raw else ApprovalOverrides()
        decision = rules.resolve(
            request.tool_name, request.tool_access_mode, request.origin.node_uid
        )
        if decision is not None:
            return ApprovalResponse(
                request.request_id, decision, feedback="Resolved by execution rule"
            )
        return await super().request_approval(request)

    async def _send_and_wait(
        self, request: ApprovalRequest, timeout: float
    ) -> ApprovalResponse | None:
        context = self._context
        base = root_key(context.root_execution_id)
        key = request_key(context.root_execution_id, request.request_id)
        ticket = canonical(
            {
                "execution_id": context.execution_id,
                "request": REQUEST.dump_python(request, mode="json"),
            }
        )
        primary_error: BaseException | None = None
        try:
            # Drain registration before closing its ticket, even if cancellation
            # arrives while Redis is acknowledging a committed CREATE.
            code = await await_owned(
                self._client.eval(
                    CREATE,
                    4,
                    key,
                    base + ":pending",
                    base + ":events",
                    base + ":cancelled",
                    ticket,
                    max(1, int(timeout * 1000)),
                    self._ttl,
                    canonical(
                        {"execution_id": context.execution_id, "data": approval_event(request)}
                    ),
                    self._max_events,
                    self._scope,
                )
            )
            if code == -2:
                return self._rejected(request)
            response_result(code)
            while not self._cancelled.is_set():
                status, payload = await self._client.eval(
                    POLL, 3, key, base + ":pending", base + ":cancelled"
                )
                if status == ApprovalStatus.RESPONDED.value:
                    return RESPONSE.validate_json(payload)
                if status == ApprovalStatus.CANCELLED.value:
                    return self._rejected(request)
                if status != ApprovalStatus.PENDING.value:
                    return None
                try:
                    await asyncio.wait_for(self._cancelled.wait(), timeout=0.1)
                except TimeoutError:
                    pass
            return self._rejected(request)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                await await_owned(
                    self._client.eval(CLOSE_PENDING, 2, key, base + ":pending", ticket)
                )
            except Exception as error:
                if primary_error is None:
                    raise
                primary_error.add_note(f"Approval cleanup also failed ({type(error).__name__})")

    @staticmethod
    def _rejected(request: ApprovalRequest) -> ApprovalResponse:
        return ApprovalResponse(
            request.request_id, ApprovalDecision.REJECT, feedback="Execution was cancelled"
        )
