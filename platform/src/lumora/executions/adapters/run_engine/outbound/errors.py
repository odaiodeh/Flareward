"""Translate native execution failures at both inbound and outbound boundaries."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps

from pydantic import ValidationError
from runengine.coordination.enums import RunFailureCode
from runengine.coordination.errors import RunContractError
from runengine.core.enums import FailureOrigin
from runengine.core.failure import FailureDescriptor
from runengine.invocation.errors import (
    InvocationApplicationError,
    InvocationContractError,
    InvocationInfrastructureError,
)

from lumora.executions.domain.models import ExecutionFailure, FailureKind
from lumora.executions.ports import ExecutionError, ExecutionMissing
from lumora.programs.domain.bindings import BindingError
from lumora.programs.state import StateContractError


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
        except (BindingError, StateContractError) as error:
            raise InvocationContractError(str(error)) from None
        except ValidationError:
            raise InvocationContractError("Execution violates a model contract") from None
        except ExecutionError as error:
            failure = FailureDescriptor(
                origin=FailureOrigin.CONTRACT
                if error.failure.kind == FailureKind.CONTRACT
                else FailureOrigin.INFRASTRUCTURE
                if error.failure.kind == FailureKind.INFRASTRUCTURE
                else FailureOrigin.APPLICATION,
                error_type=type(error).__name__,
                message=error.failure.message,
                code=error.failure.code,
                retryable=error.failure.retryable
                if error.failure.kind == FailureKind.INFRASTRUCTURE
                else None,
            )
            if error.failure.kind == FailureKind.CONTRACT:
                raise InvocationContractError(error.failure.message, failure=failure) from error
            if error.failure.kind == FailureKind.INFRASTRUCTURE:
                raise InvocationInfrastructureError(
                    error.failure.message, retryable=error.failure.retryable, failure=failure
                ) from error
            raise

    return translated
