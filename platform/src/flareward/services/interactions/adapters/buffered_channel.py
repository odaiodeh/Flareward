"""Bounded nonblocking capture for sync/async elements, with an owned async drain."""

import asyncio
import queue
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import JsonValue, TypeAdapter
from pydantic_core import to_jsonable_python

from flareward.elements.messaging.channels import SessionChannel
from flareward.executions.domain.context import ExecutionContext

PAYLOAD = TypeAdapter(dict[str, JsonValue])


class BufferedChannel(SessionChannel):
    def __init__(
        self,
        context: ExecutionContext,
        publish: Callable[[dict[str, JsonValue]], Awaitable[None]],
        *,
        capacity: int = 256,
    ) -> None:
        self._context, self._publish = context, publish
        self._queue: queue.Queue[dict[str, JsonValue]] = queue.Queue(maxsize=capacity)
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        self._closed = False
        self._failure: Exception | None = None
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str:
        return self._context.session_id

    def emit(self, data: Any) -> None:
        with self._lock:
            if self._closed:
                return
        payload = PAYLOAD.validate_python(to_jsonable_python(data))
        with self._lock:
            if self._closed:
                return
            if self._failure:
                raise RuntimeError("Stream transport failed") from self._failure
            try:
                self._queue.put_nowait(payload)
            except queue.Full as error:
                raise RuntimeError(
                    "Element stream exceeded its configured buffer capacity"
                ) from error
        self._loop.call_soon_threadsafe(self._wake.set)

    def is_active(self) -> bool:
        with self._lock:
            return not self._closed and self._failure is None

    def close(self, *, cancelled: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._loop.call_soon_threadsafe(self._wake.set)

    async def drain(self) -> None:
        try:
            while True:
                self._wake.clear()
                while True:
                    try:
                        payload = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    await self._publish(payload)
                with self._lock:
                    if self._closed and self._queue.empty():
                        return
                await self._wake.wait()
        except Exception as error:
            with self._lock:
                self._failure = error
            raise
