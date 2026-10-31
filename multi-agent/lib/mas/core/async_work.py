"""Drain owned work before propagating cancellation to its caller."""

import asyncio
from collections.abc import Awaitable, Callable


async def await_owned[T](
    operation: Awaitable[T],
    *,
    on_cancel: Callable[[], None] | None = None,
    cancel_work: bool = False,
) -> T:
    """Notify the owner and drain work before propagating caller cancellation.

    Blocking calls and acquisitions finish by default. Native async operations
    can opt into cancellation; notification precedes delivery so their cleanup
    can also release any owned blocking work.
    """
    task = asyncio.ensure_future(operation)
    cancellation: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            if cancellation is None:
                cancellation = error
                if on_cancel is not None:
                    try:
                        on_cancel()
                    except Exception as failure:
                        cancellation.add_note(f"Cancellation notification failed: {failure!r}")
                if cancel_work:
                    task.cancel()
        except Exception:
            break
    if cancellation is not None:
        if not task.cancelled() and task.exception() is not None:
            cancellation.add_note(f"Owned work also failed: {task.exception()!r}")
        raise cancellation
    return task.result()
