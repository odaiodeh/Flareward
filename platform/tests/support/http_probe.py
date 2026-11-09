"""Own a reachable HTTP endpoint and its accepted connections for an egress test."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from flareward.async_work import await_owned


@dataclass
class HttpProbe:
    port: int
    body: str
    requests: int = 0


@asynccontextmanager
async def http_probe() -> AsyncIterator[HttpProbe]:
    body = uuid4().hex
    probe = HttpProbe(0, body)
    connections: set[asyncio.Task] = set()

    async def respond(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            probe.requests += 1
            writer.write(
                (
                    f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n"
                    f"Connection: close\r\n\r\n{body}"
                ).encode()
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def accept(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.create_task(respond(reader, writer))
        connections.add(task)

    server = await asyncio.start_server(accept, "0.0.0.0", 0)
    probe.port = server.sockets[0].getsockname()[1]
    try:
        yield probe
    finally:
        server.close()
        await server.wait_closed()
        for task in connections:
            if not task.done():
                task.cancel()
        await await_owned(asyncio.gather(*connections, return_exceptions=True))
