"""The deployed CLI serves the real API, runs Programs and shuts down owned resources."""

import asyncio
import signal
import socket
from uuid import uuid4

import httpx
import pytest
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.http_programs import execute_program, publish_program
from support.processes import command_process, settings_environment
from support.scenarios import echo_graph

from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.programs.domain.models import ProgramDefinition
from flareward.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_canonical_cli_serves_and_executes_programs(tmp_path, profile):
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="memory",
        authentication="development",
        development_user="owner",
        interactions="disabled",
        element_modules=("support.elements",),
        application_modules=("support.programs",),
        execution_profiles={"thread": ThreadRunnerConfig(), "process": ProcessRunnerConfig()},
        default_execution_profile="thread",
    )
    with socket.socket() as allocation:
        allocation.bind(("127.0.0.1", 0))
        port = allocation.getsockname()[1]
    log = tmp_path / "cli.log"
    async with command_process(
        ["-m", "flareward.bootstrap.http_cli", "serve", "--host", "127.0.0.1", "--port", str(port)],
        settings_environment(settings),
        log,
        exit_codes=(0, -signal.SIGTERM),
    ) as server:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as http:
            async with asyncio.timeout(30):
                while True:
                    server.assert_running()
                    try:
                        health = await http.get("/api/health/health")
                    except httpx.ConnectError:
                        await asyncio.sleep(0.05)
                    else:
                        assert health.status_code == 200, health.text
                        break
                reference = await publish_program(
                    http,
                    ProgramDefinition(
                        program_id="cli",
                        name="CLI",
                        owner=Identity.user("owner"),
                        implementation=echo_graph(profile),
                    ),
                )
                result = await execute_program(http, reference, uuid4().hex, {"name": "cli"})
                assert result["phase"] == "completed", result
                assert result["result"] == {"answer": "greeting:cli"}
    assert "Application shutdown complete" in log.read_text()
