"""Async SSH tool with one owned, lazily connected blocking SDK client."""

import asyncio
from collections.abc import Callable
from typing import Any

import paramiko
from pydantic import BaseModel, ConfigDict, Field

from flareward.async_work import await_owned
from flareward.elements.ports.tool import BaseTool
from flareward.services.interactions.tools.models import ToolAccessMode


class CommandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cmd: str = Field(min_length=1, description="Shell command to run on the VM")


class SshExecutionError(RuntimeError):
    """An SSH operation failed; command acceptance may be unknown."""


class SshExecTool(BaseTool):
    args_schema = CommandInput
    access_mode = ToolAccessMode.WRITE

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: float = 30,
        client_factory: Callable[[], paramiko.SSHClient] | None = None,
    ) -> None:
        self._host, self._port = host, port
        self._username, self._password = username, password
        self._timeout = timeout
        self._client_factory = client_factory or paramiko.SSHClient
        self._ssh: paramiko.SSHClient | None = None
        self._lock = asyncio.Lock()
        translation = str.maketrans(".:- /", "_____")
        self.name = (
            f"ssh_exec_{host.translate(translation)}_{port}_{username.translate(translation)}"
        )
        self.description = f"Run a shell command on {host}:{port} as {username}."

    async def run(self, *args: Any, **kwargs: Any) -> str:
        command = self.args_schema(**kwargs).cmd
        async with self._lock:
            try:
                return await await_owned(asyncio.to_thread(self._execute, command))
            except Exception as error:
                raise SshExecutionError(f"SSH execution failed ({type(error).__name__})") from None

    def _connect(self) -> paramiko.SSHClient:
        self._close()
        client = self._client_factory()
        try:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                look_for_keys=False,
                allow_agent=False,
                timeout=self._timeout,
                auth_timeout=self._timeout,
                banner_timeout=self._timeout,
            )
        except BaseException:
            client.close()
            raise
        self._ssh = client
        return client

    def _execute(self, command: str) -> str:
        client = self._ssh
        transport = client.get_transport() if client is not None else None
        if client is None or transport is None or not transport.is_active():
            client = self._connect()
        _, stdout, stderr = client.exec_command(command, timeout=self._timeout)
        output, error = stdout.read().decode().strip(), stderr.read().decode().strip()
        return f"STDERR:\n{error}" if error else output

    def _close(self) -> None:
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    async def aclose(self) -> None:
        async with self._lock:
            await await_owned(asyncio.to_thread(self._close))
