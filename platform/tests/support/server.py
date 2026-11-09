"""Real loopback HTTP server using the production ASGI factory and an inherited listening socket."""

import asyncio
import signal
import socket
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path

import httpx
from pydantic import BaseModel

from support.processes import command_process, settings_environment


@asynccontextmanager
async def api_process(
    settings: BaseModel,
    log: Path,
    *,
    factory: str = "flareward.bootstrap.asgi:create_app",
    health_path: str = "/api/health/health",
    environment: Callable[[str], Mapping[str, str]] | None = None,
    listener: socket.socket | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    with nullcontext(listener) if listener is not None else socket.socket() as bound:
        if listener is None:
            bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        process_environment = settings_environment(settings)
        if environment is not None:
            process_environment.update(environment(base_url))
        async with command_process(
            [
                "-m",
                "uvicorn",
                factory,
                "--factory",
                "--fd",
                str(bound.fileno()),
            ],
            process_environment,
            log,
            pass_fds=(bound.fileno(),),
            exit_codes=(0, -signal.SIGTERM),
        ) as server:
            async with httpx.AsyncClient(base_url=base_url, timeout=30) as http:
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
