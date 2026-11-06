"""Owned, asynchronous Codex CLI invocation with bounded protocol output."""

import asyncio
import json
import os
import signal
from pathlib import Path
from tempfile import TemporaryDirectory

from mas.application.coding.contracts import (
    CodingAgentError,
    CodingRequest,
    CodingResult,
    CodingUsage,
)
from mas.core.async_work import await_owned

from mas_plugins.subprocesses import network_environment

from .config import CodexConfig
from .identifiers import CodexSandboxMode


class CodexCodingAgent:
    def __init__(
        self,
        configuration: CodexConfig,
        *,
        workspace_root: Path,
        executable: str = "codex",
        sandbox_mode: CodexSandboxMode = CodexSandboxMode.WORKSPACE_WRITE,
    ) -> None:
        self._configuration, self._executable = configuration, executable
        self._workspace_root, self._sandbox_mode = workspace_root, sandbox_mode

    async def execute(self, request: CodingRequest) -> CodingResult:
        configuration = self._configuration
        key = await asyncio.to_thread(self._api_key)
        workspace = await asyncio.to_thread(self._workspace, request.workspace)
        # Auth/session files are invocation-owned, outside the shared coding workspace.
        with TemporaryDirectory(prefix="unifai-codex-") as home:
            environment = {
                key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG"}
            }
            environment.update(network_environment(os.environ))
            environment.update(CODEX_HOME=home, CODEX_API_KEY=key)
            arguments = (
                self._executable,
                "exec",
                "--json",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--sandbox",
                self._sandbox_mode.value,
                "-c",
                'approval_policy="never"',
                "-c",
                'shell_environment_policy.inherit="none"',
                "-c",
                "shell_environment_policy.ignore_default_excludes=false",
                "-c",
                "model_reasoning_effort=" + json.dumps(configuration.reasoning_effort.value),
                "--model",
                configuration.model,
                "--cd",
                str(workspace),
                "-",
            )
            try:
                async with asyncio.timeout(configuration.timeout_seconds):
                    result = await self._invoke(arguments, environment, request.prompt)
                    return result.model_copy(
                        update={"content": result.content.replace(key, "[redacted]")}
                    )
            except TimeoutError:
                raise CodingAgentError("Coding agent exceeded its time limit") from None
            except OSError, ValueError, TypeError, KeyError, AttributeError, ExceptionGroup:
                raise CodingAgentError("Coding agent could not execute its CLI protocol") from None

    def _api_key(self) -> str:
        if self._configuration.api_key is not None:
            return self._configuration.api_key.get_secret_value()
        # Operator-only file binding is useful when a sandbox cannot access secret storage.
        path = Path(os.environ.get("UNIFAI_CODEX_API_KEY_FILE", ""))
        try:
            if not path.is_absolute():
                raise ValueError("Expected an absolute private credential path")
            value = path.read_text().strip()
            if not value:
                raise ValueError("Empty credential")
            return value
        except OSError, ValueError:
            raise CodingAgentError("Coding agent credential is unavailable") from None

    def _workspace(self, name: str) -> Path:
        root = self._workspace_root.resolve()
        workspace = (root / name).resolve()
        if not workspace.is_relative_to(root) or workspace == root:
            raise CodingAgentError("Coding workspace escapes its configured root")
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    async def _invoke(
        self, arguments: tuple[str, ...], environment: dict[str, str], prompt: str
    ) -> CodingResult:
        process: asyncio.subprocess.Process | None = None

        async def acquire() -> None:
            nonlocal process
            process = await asyncio.create_subprocess_exec(
                *arguments,
                env=environment,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

        try:
            # Finish acquisition before cancellation so the owner can always reap the process.
            await await_owned(acquire())
            assert process is not None
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(self._discard(process.stderr))
                tasks.create_task(self._input(process.stdin, prompt))
                result = await self._result(process.stdout)
                code = await process.wait()
            if code != 0:
                raise CodingAgentError("Coding agent CLI exited unsuccessfully")
            return result
        finally:
            if process is not None:
                await await_owned(self._stop(process))

    @staticmethod
    async def _input(stream: asyncio.StreamWriter, prompt: str) -> None:
        try:
            stream.write(prompt.encode())
            await stream.drain()
        except BrokenPipeError, ConnectionResetError:
            pass
        finally:
            stream.close()

    @staticmethod
    async def _discard(stream: asyncio.StreamReader) -> None:
        # Drain diagnostics without logging or retaining credentials, prompts, or commands.
        while await stream.read(8192):
            pass

    async def _result(self, stream: asyncio.StreamReader) -> CodingResult:
        content, usage = "", CodingUsage()
        size = commands = changes = 0
        completed = False
        while line := await stream.readline():
            size += len(line)
            if size > self._configuration.max_output_bytes:
                raise CodingAgentError("Coding agent exceeded its output limit")
            event = json.loads(line)
            if not isinstance(event, dict):
                raise CodingAgentError("Coding agent returned an invalid event")
            kind = event.get("type")
            if kind in {"error", "turn.failed"}:
                raise CodingAgentError("Coding agent reported a failed turn")
            item = event.get("item", {})
            if kind == "item.started" and item.get("type") == "command_execution":
                commands += 1
                if commands > self._configuration.max_commands:
                    raise CodingAgentError("Coding agent exceeded its command limit")
            if kind == "item.completed":
                if item.get("type") == "agent_message":
                    content = item["text"]
                elif item.get("type") == "file_change":
                    changes += len(item.get("changes", []))
            if kind == "turn.completed":
                usage = CodingUsage.model_validate(event.get("usage", {}))
                completed = True
        if not completed or not content:
            raise CodingAgentError("Coding agent returned no completed answer")
        return CodingResult(content=content, usage=usage, commands=commands, changes=changes)

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            async with asyncio.timeout(2):
                await process.wait()
        except TimeoutError:
            pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
