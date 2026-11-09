"""Bounded candidate evaluation inside an operator-approved execution environment."""

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from flareward.async_work import await_owned
from flareward.elements.operation import BaseOperation, OperationContext
from plugins.processes import network_environment
from plugins.testing.contracts import (
    EvaluationFailure,
    PythonFunctionConfig,
    PythonFunctionInput,
    PythonFunctionResult,
)


class CheckProtocolError(ValueError):
    """Private subprocess diagnostics are not verification evidence."""


class PythonFunctionEvaluation(BaseOperation[PythonFunctionInput, PythonFunctionResult]):
    """Return untrusted actual values; comparison belongs outside this receiver."""

    def __init__(self, config: PythonFunctionConfig, directory: Path) -> None:
        self._config, self._directory = config, directory

    @staticmethod
    async def _read(stream: asyncio.StreamReader) -> bytes:
        result = bytearray()
        while chunk := await stream.read(4096):
            if len(result) + len(chunk) > 65_536:
                raise CheckProtocolError("Check output exceeds its byte limit")
            result.extend(chunk)
        return bytes(result)

    async def _exchange(
        self, process: asyncio.subprocess.Process, request: PythonFunctionInput
    ) -> bytes:
        assert process.stdin is not None and process.stdout is not None
        assert process.stderr is not None
        cases = [case.model_dump(mode="json") for case in request.cases]

        async def write() -> None:
            assert process.stdin is not None
            process.stdin.write(json.dumps(cases, allow_nan=False).encode())
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()

        try:
            async with asyncio.TaskGroup() as tasks:
                output = tasks.create_task(self._read(process.stdout))
                tasks.create_task(self._read(process.stderr))
                tasks.create_task(write())
                await process.wait()
        except* OSError, ValueError:
            raise CheckProtocolError("Check subprocess exchange failed") from None
        return output.result()

    async def execute(
        self, request: PythonFunctionInput, context: OperationContext
    ) -> PythonFunctionResult:
        content = request.source.decoded()
        owned: TemporaryDirectory[str] | None = None
        process: asyncio.subprocess.Process | None = None

        def prepare() -> Path:
            nonlocal owned
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            owned = TemporaryDirectory(prefix="check-", dir=self._directory)
            candidate = Path(owned.name) / "candidate.py"
            candidate.write_bytes(content)
            return candidate

        async def acquire(candidate: Path) -> None:
            nonlocal process
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-S",
                str(Path(__file__).with_name("_python_worker.py")),
                str(candidate),
                self._config.function,
                cwd=candidate.parent,
                env={"PATH": os.defpath, **network_environment(os.environ)},
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

        async def release() -> None:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
            if owned is not None:
                await asyncio.to_thread(owned.cleanup)

        try:
            candidate = await await_owned(asyncio.to_thread(prepare))
            async with asyncio.timeout(self._config.timeout_seconds):
                await await_owned(acquire(candidate))
                assert process is not None
                output = await self._exchange(process, request)
            if process.returncode != 0:
                return PythonFunctionResult(failure=EvaluationFailure.EXECUTION)
            actual = json.loads(output)
            if not isinstance(actual, list) or len(actual) != len(request.cases):
                raise CheckProtocolError("Evaluation result count differs from arguments")
            return PythonFunctionResult(values=tuple(actual))
        except TimeoutError:
            return PythonFunctionResult(failure=EvaluationFailure.DEADLINE)
        except OSError:
            return PythonFunctionResult(failure=EvaluationFailure.EXECUTION)
        except ValueError:
            return PythonFunctionResult(failure=EvaluationFailure.OUTPUT)
        finally:
            await await_owned(release())
