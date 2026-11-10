"""One owned lifecycle for separately started API and worker processes."""

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path, PurePath

from pydantic import BaseModel, SecretStr
from pydantic_core import to_jsonable_python

from lumora.async_work import await_owned


def _settings_value(value: object) -> object:
    """Unwrap only the explicitly supplied test settings, including nested credentials."""
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if isinstance(value, dict):
        return {key: _settings_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_settings_value(item) for item in value]
    return value


def settings_environment(settings: BaseModel) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("LUMORA_")}
    for name, value in settings.model_dump(mode="python").items():
        if value is None:
            continue
        if isinstance(value, SecretStr):
            encoded = value.get_secret_value()
        elif isinstance(value, str | PurePath):
            encoded = str(value)
        else:
            normalized = to_jsonable_python(_settings_value(value))
            encoded = normalized if isinstance(normalized, str) else json.dumps(normalized)
        environment["LUMORA_" + name.upper()] = encoded
    environment["PYTHONPATH"] = os.pathsep.join(sys.path)
    return environment


class OwnedProcess:
    def __init__(self, process: subprocess.Popen, log: Path, exit_codes: tuple[int, ...]) -> None:
        self._process, self._log, self._exit_codes = process, log, exit_codes

    def assert_running(self) -> None:
        assert self._process.poll() is None, self._log.read_text()[-10000:]

    async def crash(self) -> None:
        self.assert_running()
        self._process.kill()
        await asyncio.to_thread(self._process.wait, timeout=5)

    async def close(self) -> None:
        running = self._process.poll() is None
        if running:
            self._process.terminate()
        try:
            await asyncio.to_thread(self._process.wait, timeout=15)
        except subprocess.TimeoutExpired:
            self._process.kill()
            await asyncio.to_thread(self._process.wait, timeout=5)
            raise AssertionError("Owned process did not shut down gracefully") from None
        if running:
            assert self._process.returncode in self._exit_codes, self._log.read_text()[-10000:]


@asynccontextmanager
async def command_process(
    arguments: Sequence[str],
    environment: Mapping[str, str],
    log: Path,
    *,
    pass_fds: tuple[int, ...] = (),
    exit_codes: tuple[int, ...] = (0,),
) -> AsyncIterator[OwnedProcess]:
    with log.open("w") as output:
        owned = OwnedProcess(
            subprocess.Popen(
                [sys.executable, *arguments],
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                pass_fds=pass_fds,
            ),
            log,
            exit_codes,
        )
        try:
            yield owned
        finally:
            await await_owned(owned.close())
