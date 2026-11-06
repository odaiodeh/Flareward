"""Redis failures cross application ports as domain failures, without retrying tool effects."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any

from mas.application.execution.ports import ExecutionError
from mas.domain.execution.models import ExecutionFailure, FailureKind
from redis.exceptions import RedisError


def unavailable() -> ExecutionError:
    return ExecutionError(
        ExecutionFailure(
            kind=FailureKind.INFRASTRUCTURE,
            message="Execution interaction transport is unavailable",
            code="interaction_transport_unavailable",
            retryable=False,
        )
    )


def redis_async[**P, R](
    operation: Callable[P, Awaitable[R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    @wraps(operation)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await operation(*args, **kwargs)
        except RedisError as error:
            raise unavailable() from error

    return guarded
