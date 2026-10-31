"""Translate native execution failures at both inbound and outbound boundaries."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps

from mas.execution.models import ExecutionFailure, FailureKind
from mas.execution.ports import ExecutionError, ExecutionMissing
from runengine.coordination.enums import RunFailureCode
from runengine.coordination.errors import RunContractError
from runengine.invocation.errors import (
    InvocationApplicationError,
    InvocationContractError,
    InvocationInfrastructureError,
)


def portable_failure(
    error: InvocationApplicationError | InvocationContractError | InvocationInfrastructureError,
) -> ExecutionFailure:
    if isinstance(error, InvocationContractError):
        kind = FailureKind.CONTRACT
    elif isinstance(error, InvocationInfrastructureError):
        kind = FailureKind.INFRASTRUCTURE
    else:
        kind = FailureKind.APPLICATION
    failure = error.failure
    return ExecutionFailure(
        kind=kind,
        message=str(error),
        code=str(failure.code) if failure and failure.code else None,
        retryable=bool(failure.retryable)
        if failure is not None
        else (error.retryable if isinstance(error, InvocationInfrastructureError) else False),
    )


@asynccontextmanager
async def engine_errors() -> AsyncIterator[None]:
    try:
        yield
    except RunContractError as error:
        if error.code == RunFailureCode.NOT_FOUND:
            raise ExecutionMissing(str(error)) from error
        raise ExecutionError(portable_failure(error)) from error
    except KeyError as error:
        raise ExecutionMissing(str(error)) from error
    except (
        InvocationApplicationError,
        InvocationContractError,
        InvocationInfrastructureError,
    ) as error:
        raise ExecutionError(portable_failure(error)) from error


def application_errors[**P, R](operation: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(operation)
    async def translated(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await operation(*args, **kwargs)
        except ExecutionError as error:
            if error.failure.kind == FailureKind.CONTRACT:
                raise InvocationContractError(error.failure.message) from error
            if error.failure.kind == FailureKind.INFRASTRUCTURE:
                raise InvocationInfrastructureError(
                    error.failure.message, retryable=error.failure.retryable
                ) from error
            raise

    return translated
