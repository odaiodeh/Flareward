"""Thin installed entrypoint; application implementations receive only application ports."""

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import JsonValue, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import InstanceRef
from runengine.invocation.errors import InvocationContractError
from runengine.programs.graph.entrypoint import run_graph
from runengine.programs.graph.inputs import GraphProgramInput

from lumora.executions.adapters.run_engine.outbound.budgets import BudgetedOperations
from lumora.executions.adapters.run_engine.outbound.errors import application_errors
from lumora.executions.adapters.run_engine.outbound.observation import ObservedOperations
from lumora.executions.adapters.run_engine.outbound.runtime import RunEngineProgramRuntime
from lumora.executions.adapters.run_engine.shared.context import current_context, graph_context
from lumora.executions.adapters.run_engine.shared.models import (
    MappingConfiguration,
    PreparedGraph,
    ProgramPayload,
    ProjectionConfiguration,
)
from lumora.executions.adapters.run_engine.shared.state import ProgramGraphState
from lumora.json_values import portable_json
from lumora.programs.domain.bindings import BindingError, project
from lumora.programs.invocation import CoordinatorInvoker, ProgramInvocationContractError
from lumora.programs.state import StateContractError

__runengine_contract__ = "lumora-program-v12"


@application_errors
async def execute_program(operations: CoordinationOperations, data: JsonValue) -> JsonValue:
    payload = ProgramPayload.model_validate(data)
    context = current_context(payload.context, operations.run_id)
    if payload.work_budget is not None:
        budgeted = BudgetedOperations(
            operations, payload.work_budget, context, payload.cancellation
        )
        await budgeted.initialize()
        operations = budgeted
    observed = ObservedOperations(
        operations,
        context.execution_id,
        payload.implementation.sites if isinstance(payload.implementation, PreparedGraph) else None,
    )
    await observed.initialize()
    operations = observed
    output: JsonValue
    try:
        for schema in payload.interface.input_schemas:
            Draft202012Validator(schema, registry=Registry()).validate(payload.inputs)
    except SchemaValidationError, Unresolvable, RecursionError:
        raise InvocationContractError("Program input violates its contract") from None
    implementation = payload.implementation
    if isinstance(implementation, PreparedGraph):
        request = RunRequest.model_validate(implementation.request)
        specification = graph_context(GraphProgramInput.model_validate(request.input), context)
        state_type = specification.state.resolve()
        if not issubclass(state_type, ProgramGraphState):
            raise InvocationContractError("Graph state requires an installed Program state adapter")
        initial = state_type.model_validate(
            {**project(implementation.inputs, payload.inputs), "input": payload.inputs}
        )
        specification = specification.model_copy(
            update={"state": InstanceRef.from_instance(initial)}
        )
        result = await run_graph(operations, specification.model_dump(mode="json"))
        output = project(implementation.outputs, result)
    else:
        try:
            # Installed declarations are preloaded by the worker. Resolving their
            # identities is deterministic; workflow coordination cannot spawn threads.
            registration = implementation.call.resolve()
        except ValueError, TypeError:
            raise InvocationContractError("Installed Program declaration is invalid") from None
        runtime = RunEngineProgramRuntime(
            operations,
            implementation.children,
            payload.specifications,
            context,
            payload.placement,
            payload.receiver,
            payload.cancellation,
        )
        try:
            output = await CoordinatorInvoker(registration, payload.interface).invoke(
                runtime, payload.inputs, implementation.configuration
            )
        except ProgramInvocationContractError as error:
            raise InvocationContractError(str(error)) from None
    try:
        output = portable_json(output)
    except ValidationError:
        raise InvocationContractError("Program output must be portable JSON") from None
    try:
        for schema in payload.interface.output_schemas:
            Draft202012Validator(schema, registry=Registry()).validate(output)
    except SchemaValidationError, Unresolvable, RecursionError:
        raise InvocationContractError("Program output violates its contract") from None
    return output


def map_program_inputs(
    state: ProgramGraphState,
    template: dict[str, JsonValue],
    *,
    bindings: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    configuration = ProjectionConfiguration.model_validate({"bindings": bindings})
    result = dict(template)
    try:
        result["inputs"] = project(configuration.bindings, state.serialize())
    except BindingError as error:
        raise InvocationContractError(str(error)) from None
    return result


def map_program_outputs(
    state: ProgramGraphState, result: JsonValue, *, bindings: dict[str, JsonValue], key: str
) -> ProgramGraphState:
    configuration = MappingConfiguration.model_validate({"bindings": bindings})
    try:
        changes = project(configuration.bindings, result)
    except BindingError as error:
        raise InvocationContractError(str(error)) from None
    try:
        return state.record_result(key, result, changes)
    except StateContractError as error:
        raise InvocationContractError(str(error)) from None
