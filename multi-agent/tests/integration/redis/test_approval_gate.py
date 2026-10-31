"""Native approval cancellation owns registration and only its matching ticket."""

import asyncio
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from mas.core.async_work import await_owned
from mas.core.execution_context import ExecutionContext
from mas.core.hitl.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalType,
    HITLConfig,
    RequestOrigin,
    ToolAccessMode,
)
from mas.core.identity import Identity
from mas.interactions.models import ApprovalTicket, InteractionConflict
from outbound.interactions.redis_gate import RedisApprovalGate
from outbound.interactions.redis_store import RedisInteractionStore
from outbound.interactions.wire import CREATE, request_key, root_key
from outbound.redis_client import owned_redis


@pytest.fixture
async def gate_case():
    uri = os.environ.get("UNIFAI_TEST_REDIS_URI")
    if not uri:
        pytest.skip("Set UNIFAI_TEST_REDIS_URI for actual Redis approval contracts")
    root = "approval-" + uuid4().hex
    context = ExecutionContext(
        identity=Identity.user("reviewer"),
        execution_id=root,
        root_execution_id=root,
    )
    async with owned_redis(uri, decode_responses=True) as client:
        await client.ping()
        store = RedisInteractionStore(client)
        gate = RedisApprovalGate(client, context, asyncio.Event(), HITLConfig(timeout_seconds=30))
        try:
            yield client, context, gate, store
        finally:
            keys = [key async for key in client.scan_iter(match=root_key(root) + ":*")]
            if keys:
                await await_owned(client.delete(*keys))


def approval(request_id: str) -> ApprovalRequest:
    return ApprovalRequest(
        request_id,
        ApprovalType.TOOL_EXECUTION,
        RequestOrigin("agent", "Agent", "session"),
        "write",
        {},
        "Review a deterministic write",
        ToolAccessMode.WRITE,
    )


async def wait_pending(
    store: RedisInteractionStore,
    root: str,
    count: int,
) -> list[ApprovalTicket]:
    async with asyncio.timeout(3):
        while True:
            tickets = await store.pending(root)
            if len(tickets) == count:
                return tickets
            await asyncio.sleep(0.01)


async def test_cancelled_registration_finishes_before_its_ticket_is_closed(gate_case, monkeypatch):
    client, context, gate, store = gate_case
    registered, release = asyncio.Event(), asyncio.Event()
    evaluate = client.eval

    async def hold_registration(script, *args, **kwargs):
        result = await evaluate(script, *args, **kwargs)
        if script == CREATE:
            registered.set()
            await release.wait()
        return result

    monkeypatch.setattr(client, "eval", hold_registration)
    request = approval("held")
    async with asyncio.TaskGroup() as work:
        task = work.create_task(gate.request_approval(request))
        try:
            await asyncio.wait_for(registered.wait(), timeout=3)
            task.cancel("original cancellation")
            await asyncio.sleep(0)
            task.cancel("repeated cancellation")
            assert len(await store.pending(context.execution_id)) == 1
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError, match="original cancellation"):
                await task
        finally:
            release.set()
    assert await store.pending(context.execution_id) == []
    key = request_key(context.execution_id, request.request_id)
    assert await client.hget(key, "status") == "cancelled"
    with pytest.raises(InteractionConflict):
        await store.respond(
            context.execution_id,
            ApprovalResponse(request.request_id, ApprovalDecision.APPROVE),
        )
    assert await client.hget(key, "status") == "cancelled"


async def test_conflicting_registration_does_not_close_another_request(gate_case):
    _, context, gate, store = gate_case
    request = approval("original")
    async with asyncio.TaskGroup() as work:
        task = work.create_task(gate.request_approval(request))
        await wait_pending(store, context.execution_id, 1)
        with pytest.raises(InteractionConflict):
            await gate.request_approval(replace(request, tool_args={"different": True}))
        tickets = await store.pending(context.execution_id)
        assert [ticket.request for ticket in tickets] == [request]
        await store.respond(
            context.execution_id,
            ApprovalResponse(request.request_id, ApprovalDecision.APPROVE),
        )
        assert (await task).approved


async def test_cancelling_one_wait_preserves_a_sibling_ticket(gate_case):
    _, context, gate, store = gate_case
    async with asyncio.TaskGroup() as work:
        left = work.create_task(gate.request_approval(approval("left")))
        right = work.create_task(gate.request_approval(approval("right")))
        await wait_pending(store, context.execution_id, 2)
        left.cancel()
        with pytest.raises(asyncio.CancelledError):
            await left
        tickets = await store.pending(context.execution_id)
        assert [ticket.request.request_id for ticket in tickets] == ["right"]
        await store.respond(
            context.execution_id, ApprovalResponse("right", ApprovalDecision.APPROVE)
        )
        assert (await right).approved
