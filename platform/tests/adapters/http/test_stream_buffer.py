"""The synchronous channel contract stays nonblocking and owns its async transport drain."""

import asyncio

import pytest

from lumora.elements.messaging.domain.messages import ChatMessage, Role
from lumora.executions.domain.context import ExecutionContext
from lumora.services.identity.domain import Identity
from lumora.services.interactions.adapters.buffered_channel import BufferedChannel


async def test_buffer_normalizes_domain_values_and_drains_before_close():
    emitted = []

    async def publish(data):
        await asyncio.sleep(0)
        emitted.append(data)

    context = ExecutionContext(identity=Identity.user("owner"))
    channel = BufferedChannel(context, publish)
    task = asyncio.create_task(channel.drain())
    channel.emit({"messages": [ChatMessage(role=Role.USER, content="portable")]})
    channel.close()
    await task
    assert emitted[0]["messages"][0]["content"] == "portable"
    assert not channel.is_active()
    channel.emit(object())
    channel.close()


async def test_buffer_refuses_overflow_without_blocking_the_event_loop():
    async def publish(data):
        pass

    channel = BufferedChannel(
        ExecutionContext(identity=Identity.user("owner")), publish, capacity=1
    )
    channel.emit({"type": "first"})
    with pytest.raises(RuntimeError, match="buffer capacity"):
        channel.emit({"type": "overflow"})
    channel.close()
    await channel.drain()


async def test_transport_failure_is_reported_and_never_silently_drops_following_events():
    async def unavailable(data):
        raise OSError("Test transport failure")

    channel = BufferedChannel(ExecutionContext(identity=Identity.user("owner")), unavailable)
    channel.emit({"type": "first"})
    with pytest.raises(OSError, match="transport failure"):
        await channel.drain()
    with pytest.raises(RuntimeError, match="transport failed"):
        channel.emit({"type": "later"})
    channel.close()
