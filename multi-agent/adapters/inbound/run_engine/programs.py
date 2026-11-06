"""Thin installed entrypoint; application implementations receive only application ports."""

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from mas.application.programs.invocation import ApplicationInvoker, ProgramInvocationContractError
from mas.application.programs.state import StateContractError
from mas.domain.json_values import portable_json
from mas.domain.programs.bindings import BindingError, project
from outbound.run_engine.budgets import BudgetedOperations
from outbound.run_engine.errors import application_errors
from outbound.run_engine.runtime import RunEngineProgramRuntime
from pydantic import JsonValue, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable
from run_engine.context import current_context, graph_context
from run_engine.models import MappingConfiguration, ProgramPayload, ProjectionConfiguration
from run_engine.state import ProgramGraphState
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import InstanceRef
from runengine.invocation.errors import InvocationContractError
from runengine.programs.graph.entrypoint import run_graph
from runengine.programs.graph.inputs import GraphProgramInput

__runengine_contract__ = "unifai-program-v5"


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
    output: JsonValue
    try:
        Draft202012Validator(payload.input_schema, registry=Registry()).validate(payload.inputs)
    except SchemaValidationError, Unresolvable, RecursionError:
        raise InvocationContractError("Program input violates its contract") from None
    if payload.graph_request is not None:
        request = RunRequest.model_validate(payload.graph_request)
        specification = graph_context(GraphProgramInput.model_validate(request.input), context)
        initial = ProgramGraphState.model_validate(
            {**project(payload.graph_inputs, payload.inputs), "input": payload.inputs}
        )
        specification = specification.model_copy(
            update={"state": InstanceRef.from_instance(initial)}
        )
        result = await run_graph(operations, specification.model_dump(mode="json"))
        output = project(payload.graph_outputs, result)
    else:
        if payload.application is None:
            raise ValueError("Application program implementation is missing")
        try:
            # Installed declarations are preloaded by the worker. Resolving their
            # identities is deterministic; workflow coordination cannot spawn threads.
            registration = payload.application.resolve()
        except ValueError, TypeError:
            raise InvocationContractError("Installed Program declaration is invalid") from None
        runtime = RunEngineProgramRuntime(
            operations,
            payload.children,
            payload.specifications,
            context,
            payload.placement,
            payload.receiver,
            payload.cancellation,
        )
        try:
            output = await ApplicationInvoker(registration).invoke(
                runtime, payload.inputs, payload.configuration
            )
        except ProgramInvocationContractError as error:
            raise InvocationContractError(str(error)) from None
    try:
        output = portable_json(output)
    except ValidationError:
        raise InvocationContractError("Program output must be portable JSON") from None
    try:
        Draft202012Validator(payload.output_schema, registry=Registry()).validate(output)
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
