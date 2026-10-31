"""Real loopback HTTP server using the production ASGI factory and an inherited listening socket."""

import asyncio
import signal
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from pydantic import BaseModel

from support.processes import command_process, settings_environment


@asynccontextmanager
async def api_process(
    settings: BaseModel,
    log: Path,
    *,
    factory: str = "bootstrap.asgi:create_app",
    health_path: str = "/api/health/health",
) -> AsyncIterator[httpx.AsyncClient]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        async with command_process(
            [
                "-m",
                "uvicorn",
                factory,
                "--factory",
                "--fd",
                str(listener.fileno()),
            ],
            settings_environment(settings),
            log,
            pass_fds=(listener.fileno(),),
            exit_codes=(0, -signal.SIGTERM),
        ) as server:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30) as http:
                async with asyncio.timeout(30):
                    while True:
                        server.assert_running()
                        try:
                            ready = await http.get(health_path)
                        except httpx.ConnectError:
                            await asyncio.sleep(0.05)
                        else:
                            assert ready.status_code == 200, ready.text
                            break
                yield http
        assert "Application shutdown complete" in log.read_text(), log.read_text()[-10000:]
