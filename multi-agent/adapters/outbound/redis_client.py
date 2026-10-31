"""Own Redis clients and release closed pool entries before an unrelated thread collects them."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mas.core.async_work import await_owned
from redis.asyncio import Redis


@asynccontextmanager
async def owned_redis(url: str, **options: Any) -> AsyncIterator[Redis]:
    client = Redis.from_url(url, **options)

    async def close() -> None:
        await client.aclose(close_connection_pool=True)
        # aclose disconnects sockets but retains closed connections in the pool.
        # Its finalizer lazily imports metrics, possibly during Temporal replay's
        # garbage collection. Reset this owned, drained pool here instead.
        client.connection_pool.reset()

    try:
        yield client
    finally:
        await await_owned(close())
