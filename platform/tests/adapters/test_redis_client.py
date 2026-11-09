"""Cancelled owner cleanup drains Redis closure before resetting its connection pool."""

import asyncio
from unittest.mock import create_autospec, patch

from redis.asyncio import ConnectionPool, Redis

from flareward.services.connections.adapters.redis import owned_redis


async def test_cancelled_redis_cleanup_finishes_before_pool_reset():
    client = create_autospec(Redis, instance=True)
    client.connection_pool = create_autospec(ConnectionPool, instance=True)
    entered, release = asyncio.Event(), asyncio.Event()

    async def close(**kwargs):
        entered.set()
        await release.wait()

    client.aclose.side_effect = close

    async def owner():
        async with owned_redis("redis://unused.invalid"):
            pass

    with patch("flareward.services.connections.adapters.redis.Redis.from_url", return_value=client):
        task = asyncio.create_task(owner())
        try:
            async with asyncio.timeout(5):
                await entered.wait()
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done()
                client.connection_pool.reset.assert_not_called()
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled()
    client.connection_pool.reset.assert_called_once()
