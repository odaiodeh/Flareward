"""Receiver-local dependency construction and execution of existing Flareward elements."""

import asyncio
import inspect
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager

from pydantic import JsonValue, ValidationError
from runengine.core.failure import FailureDescriptor
from runengine.invocation.errors import (
    InvocationApplicationError,
    InvocationContractError,
    InvocationInfrastructureError,
)

from flareward.async_work import await_owned
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.condition import ConditionResultError, normalize_condition_result
from flareward.elements.construction.builder import BuiltElement, ElementBundleBuilder
from flareward.elements.construction.context import ElementBuildContext
from flareward.elements.construction.runtime import ElementRuntime
from flareward.elements.operation import (
    BaseOperation,
    OperationContext,
    OperationContractError,
    OperationInvoker,
)
from flareward.elements.specification import BaseElementSpec
from flareward.executions.adapters.run_engine.outbound.errors import application_errors
from flareward.executions.adapters.run_engine.shared.models import (
    ElementCall,
    MappingConfiguration,
    ProjectionConfiguration,
)
from flareward.executions.adapters.run_engine.shared.state import (
    AgentProgramGraphState,
    ProgramGraphState,
)
from flareward.executions.context import ExecutionContextHolder
from flareward.executions.ports import ExecutionError
from flareward.programs.domain.bindings import project
from flareward.programs.graph.runtime_binder import NodeRuntimeBinder
from flareward.programs.graph.state.graph_state import GraphState
from flareward.programs.graph_elements import GraphElementSpec, SupportsStepContext
from flareward.programs.state import StateContractError
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.tracing import NoOpTracingService

__runengine_contract__ = "flareward-elements-v4"


@asynccontextmanager
async def default_runtime(holder: ExecutionContextHolder) -> AsyncIterator[ElementRuntime]:
    yield ElementRuntime(
        ElementBuildContext(execution_ctx=holder, tracing_service=NoOpTracingService())
    )


@asynccontextmanager
async def constructed_element(
    request: ElementCall,
) -> AsyncIterator[tuple[BuiltElement, ElementRuntime]]:
    registry = ElementRegistry()
    for reference in request.specifications:
        specification = reference.resolve()
        if not isinstance(specification, type) or not issubclass(specification, BaseElementSpec):
            raise InvocationContractError("Installed element specification is invalid")
        registry.register_spec_class(specification)
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
            if request.bundle.root.category == ResourceCategory.OPERATION:
                if not isinstance(element, BaseOperation):
                    raise InvocationContractError(
                        "Configured operation must implement BaseOperation"
                    )
            else:
                if not callable(element):
                    raise InvocationContractError("Configured graph element is not executable")
                if isinstance(element, SupportsStepContext):
                    element.set_context(request.graph_step)
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
                        "invocation_key": request.key,
                        **(
                            {"node_uid": request.graph_step.uid} if request.step is not None else {}
                        ),
                    },
                ):
                    yield built, runtime
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
            if isinstance(error, (InvocationContractError, StateContractError, ValidationError)):
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
    native_async = inspect.iscoroutinefunction(element) or inspect.iscoroutinefunction(
        getattr(element, "__call__", None)
    )
    if native_async:
        result = element(*args, **kwargs)
    else:
        result = await await_owned(asyncio.to_thread(element, *args, **kwargs), on_cancel=on_cancel)
    if inspect.isawaitable(result):
        return await await_owned(result, on_cancel=on_cancel, cancel_work=True)
    return result


async def invoke_element(*, inputs: JsonValue, call: dict[str, JsonValue]) -> JsonValue:
    request = ElementCall.model_validate(call)
    if request.bundle.root.category == ResourceCategory.OPERATION:
        return await invoke_operation(inputs=inputs, call=call)
    result = await execute_element(AgentProgramGraphState.model_validate(inputs), call=call)
    return result.serialize()


@application_errors
async def invoke_operation(*, inputs: JsonValue, call: dict[str, JsonValue]) -> JsonValue:
    request = ElementCall.model_validate(call)
    async with constructed_element(request) as (built, runtime):
        try:
            return await call_element(
                OperationInvoker(built.specification).invoke,
                runtime.cancel,
                built.element,
                inputs,
                OperationContext(execution=request.context, key=request.key),
            )
        except OperationContractError as error:
            raise InvocationContractError(str(error)) from None


@application_errors
async def execute_operation(
    state: ProgramGraphState,
    *,
    call: dict[str, JsonValue],
    inputs: dict[str, JsonValue],
    outputs: dict[str, JsonValue],
) -> ProgramGraphState:
    input_mapping = ProjectionConfiguration.model_validate({"bindings": inputs})
    output_mapping = MappingConfiguration.model_validate({"bindings": outputs})
    result = await invoke_operation(
        inputs=project(input_mapping.bindings, state.serialize()), call=call
    )
    return state.record_result(
        ElementCall.model_validate(call).key, result, project(output_mapping.bindings, result)
    )


@application_errors
async def execute_element(
    state: ProgramGraphState,
    *,
    call: dict[str, JsonValue],
) -> ProgramGraphState:
    request = ElementCall.model_validate(call)
    async with constructed_element(request) as (built, runtime):
        result = await call_element(
            built.element, runtime.cancel, GraphState.model_validate(state.serialize()), config={}
        )
        if not isinstance(result, GraphState):
            raise InvocationContractError("Element must return application graph state")
        writes = GraphElementSpec.require(built.specification).writes
        if not isinstance(state, AgentProgramGraphState):
            raise InvocationContractError("State-based nodes require the agent state adapter")
        return state.accept_node(result, writes=writes)


@application_errors
async def evaluate_condition(
    state: ProgramGraphState,
    *,
    call: dict[str, JsonValue],
) -> str | list[str]:
    request = ElementCall.model_validate(call)
    async with constructed_element(request) as (built, runtime):
        result = await call_element(
            built.element, runtime.cancel, GraphState.model_validate(state.serialize())
        )
    try:
        return normalize_condition_result(result, request.graph_step.branches)
    except ConditionResultError as error:
        raise InvocationContractError(str(error)) from None
