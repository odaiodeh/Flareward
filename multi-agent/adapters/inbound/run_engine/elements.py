"""Receiver-local dependency construction and execution of existing UnifAI elements."""

import asyncio
import inspect
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import cast

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.condition import ConditionResultError, normalize_condition_result
from mas.application.elements.construction.builder import ElementBundleBuilder
from mas.application.elements.construction.runtime import ElementRuntime
from mas.core.async_work import await_owned
from mas.core.contracts import SupportsStepContext
from mas.core.element_deps import ElementBuildContext
from mas.core.execution_context import ExecutionContextHolder
from mas.core.runtime_binder import NodeRuntimeBinder
from mas.core.tracing import NoOpTracingService
from mas.execution.ports import ExecutionError
from mas.graph.state.graph_state import GraphState
from outbound.run_engine.errors import application_errors
from pydantic import JsonValue
from run_engine.models import ElementCall
from run_engine.state import ProgramGraphState
from runengine.core.failure import FailureDescriptor
from runengine.invocation.errors import (
    InvocationApplicationError,
    InvocationContractError,
    InvocationInfrastructureError,
)

__runengine_contract__ = "unifai-elements-v1"


@asynccontextmanager
async def default_runtime(holder: ExecutionContextHolder) -> AsyncIterator[ElementRuntime]:
    yield ElementRuntime(
        ElementBuildContext(execution_ctx=holder, tracing_service=NoOpTracingService())
    )


@asynccontextmanager
async def constructed_element(
    request: ElementCall,
) -> AsyncIterator[tuple[Callable[..., object], ElementRuntime]]:
    registry = ElementRegistry()
    for reference in request.specifications:
        registry.register_spec_class(reference.resolve())
    holder = ExecutionContextHolder()
    holder.context = request.context
    manager = request.receiver.resolve()(holder) if request.receiver else default_runtime(holder)
    resources = AsyncExitStack()
    protected = False
    try:
        runtime = await await_owned(resources.enter_async_context(manager))
        if not isinstance(runtime, ElementRuntime) or runtime.build.execution_ctx is not holder:
            raise InvocationContractError(
                "Receiver must supply ElementRuntime using its execution holder"
            )
        tracing = runtime.build.tracing_service or NoOpTracingService()

        async def flush() -> None:
            await asyncio.to_thread(tracing.flush)

        resources.push_async_callback(flush)
        async with ElementBundleBuilder(registry).build(request.bundle, runtime.build) as built:
            protected = built.protected
            element = built.element
            if not callable(element):
                raise InvocationContractError("Configured graph element is not executable")
            if isinstance(element, SupportsStepContext):
                element.set_context(request.step)
            binder = NodeRuntimeBinder.default()
            try:
                binder.bind(element, runtime.bindings)
                with tracing.trace_session(
                    session_id=request.context.session_id,
                    user_id=request.context.identity_id,
                    metadata={
                        "execution_id": request.context.execution_id,
                        "root_execution_id": request.context.root_execution_id,
                        "parent_execution_id": request.context.parent_execution_id,
                        "node_uid": request.step.uid,
                    },
                ):
                    yield element, runtime
            finally:
                binder.unbind(element)
    except Exception as error:
        if protected:
            message = f"Protected element invocation failed ({type(error).__name__})"
            if isinstance(error, ExecutionError):
                raise ExecutionError(
                    error.failure.model_copy(update={"message": message, "code": None})
                ) from None
            if isinstance(error, InvocationInfrastructureError):
                raise InvocationInfrastructureError(message, retryable=error.retryable) from None
            if isinstance(error, InvocationContractError):
                raise InvocationContractError(message) from None
            failure = (
                error.failure
                if isinstance(error, InvocationApplicationError)
                else (FailureDescriptor.from_exception(error))
            )
            raise InvocationApplicationError(
                failure.model_copy(
                    update={
                        "message": message,
                        "details": {},
                        "code": None,
                    }
                )
            ) from None
        raise
    finally:
        await await_owned(resources.__aexit__(*sys.exc_info()))


async def call_element[**P, R](
    element: Callable[P, R | Awaitable[R]],
    on_cancel: Callable[[], None] | None,
    *args: P.args,
    **kwargs: P.kwargs,
) -> R:
    """Await native async elements; keep synchronous legacy work off the receiver loop."""
    if inspect.iscoroutinefunction(element) or inspect.iscoroutinefunction(element.__call__):
        result = element(*args, **kwargs)
    else:
        result = await await_owned(asyncio.to_thread(element, *args, **kwargs), on_cancel=on_cancel)
    if inspect.isawaitable(result):
        return await await_owned(result, on_cancel=on_cancel, cancel_work=True)
    return cast(R, result)


async def invoke_element(
    *, inputs: dict[str, JsonValue], call: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    result = await execute_element(ProgramGraphState.model_validate(inputs), call=call)
    return result.serialize()


@application_errors
async def execute_element(
    state: ProgramGraphState,
    *,
    call: dict[str, JsonValue],
) -> ProgramGraphState:
    request = ElementCall.model_validate(call)
    async with constructed_element(request) as (element, runtime):
        result = await call_element(element, runtime.cancel, state.model_copy(deep=True), config={})
        if not isinstance(result, GraphState):
            raise InvocationContractError("Element must return application graph state")
        return ProgramGraphState.model_validate({**state.serialize(), **result.serialize()})


@application_errors
async def evaluate_condition(
    state: ProgramGraphState,
    *,
    call: dict[str, JsonValue],
) -> str | list[str]:
    request = ElementCall.model_validate(call)
    async with constructed_element(request) as (element, runtime):
        result = await call_element(element, runtime.cancel, state.model_copy(deep=True))
    try:
        return normalize_condition_result(result, request.step.branches)
    except ConditionResultError as error:
        raise InvocationContractError(str(error)) from None
