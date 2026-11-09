"""Receiver cancellation releases owned work before element resources can close."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from flareward.async_work import await_owned
from flareward.executions.adapters.run_engine.inbound.elements import call_element


class AsyncElement:
    def __init__(self, run: Callable[[], Awaitable[str]]) -> None:
        self._run = run

    async def __call__(self) -> str:
        return await self._run()


@pytest.mark.parametrize("shape", ["function", "object", "returned_awaitable"])
async def test_async_cancellation_notifies_owner_and_drains_element_cleanup(shape):
    started, release, cleaning, finish_cleanup = (asyncio.Event() for _ in range(4))
    events = []

    def cancel() -> None:
        events.append("notified")
        release.set()

    async def run() -> str:
        started.set()
        try:
            # A native element can own a non-cancellable operation, such as a
            # blocking SDK call. Its owner must signal release before draining.
            await await_owned(release.wait())
            return "finished"
        finally:
            events.append("cleanup_started")
            cleaning.set()
            await finish_cleanup.wait()
            events.append("cleanup_finished")

    def returned_awaitable() -> Awaitable[str]:
        return run()

    element = {
        "function": run,
        "object": AsyncElement(run),
        "returned_awaitable": returned_awaitable,
    }[shape]
    task = asyncio.create_task(call_element(element, cancel))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel("original cancellation")
        await asyncio.wait_for(cleaning.wait(), timeout=2)
        assert events == ["notified", "cleanup_started"]
        task.cancel("repeated cancellation")
        await asyncio.sleep(0)
        assert not task.done()
        finish_cleanup.set()
        with pytest.raises(asyncio.CancelledError, match="original cancellation"):
            await task
        assert events == ["notified", "cleanup_started", "cleanup_finished"]
    finally:
        release.set()
        finish_cleanup.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_async_element_failure_is_not_converted_to_cancellation():
    def cancel() -> None:
        pytest.fail("An element failure must not notify cancellation")

    async def run() -> str:
        raise ValueError("element failed")

    with pytest.raises(ValueError, match="element failed"):
        await call_element(run, cancel)
