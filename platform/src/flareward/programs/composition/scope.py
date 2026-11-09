"""Own transient coordination tasks and admitted child calls, not infrastructure leases."""

import asyncio
import logging
from collections.abc import Awaitable, Iterable
from types import TracebackType
from typing import Self

from pydantic import JsonValue

from flareward.programs.ports import ChildExecution, ProgramRuntime

logger = logging.getLogger(__name__)


class ChildCalls:
    def __init__(self, runtime: ProgramRuntime) -> None:
        self._runtime = runtime
        self._active: dict[str, ChildExecution] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if error is not None and self._active:
            outcomes = await asyncio.gather(
                *(child.cancel() for child in self._active.values()), return_exceptions=True
            )
            if any(isinstance(value, BaseException) for value in outcomes):
                logger.warning("Composition child cancellation remains unconfirmed")

    async def call(self, name: str, inputs: JsonValue, *, key: str) -> tuple[str, JsonValue]:
        child = await self._runtime.start_child(name, inputs, key=key)
        self._active[key] = child
        value = await child.result()
        self._active.pop(key)
        return child.execution_id, value

    async def gather(self, work: Iterable[Awaitable[None]]) -> None:
        tasks = [asyncio.ensure_future(item) for item in work]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
