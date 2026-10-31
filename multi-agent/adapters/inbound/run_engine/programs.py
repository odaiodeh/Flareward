"""Thin installed entrypoint; application implementations receive only application ports."""

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from mas.programs.bindings import project
from mas.programs.models import GraphDefinition
from outbound.run_engine.errors import application_errors
from outbound.run_engine.runtime import RunEngineProgramRuntime
from pydantic import JsonValue
from run_engine.context import current_context, graph_context
from run_engine.models import MappingConfiguration, ProgramPayload
from run_engine.state import ProgramGraphState
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import InstanceRef
from runengine.invocation.errors import InvocationContractError
from runengine.programs.graph.entrypoint import run_graph
from runengine.programs.graph.inputs import GraphProgramInput

__runengine_contract__ = "unifai-program-v1"


@application_errors
async def execute_program(operations: CoordinationOperations, data: JsonValue) -> JsonValue:
    payload = ProgramPayload.model_validate(data)
    context = current_context(payload.context, operations.run_id)
    definition = payload.revision.definition
    try:
        Draft202012Validator(definition.input_schema).validate(payload.inputs)
    except SchemaValidationError as error:
        raise InvocationContractError(
            f"Program input violates its contract: {error.message}"
        ) from error
    implementation = definition.implementation
    if isinstance(implementation, GraphDefinition):
        request = RunRequest.model_validate(payload.graph_request)
        specification = graph_context(GraphProgramInput.model_validate(request.input), context)
        initial = ProgramGraphState.model_validate(project(implementation.inputs, payload.inputs))
        specification = specification.model_copy(
            update={"state": InstanceRef.from_instance(initial)}
        )
        result = await run_graph(operations, specification.model_dump(mode="json"))
        output = project(implementation.outputs, result)
    else:
        if payload.application_function is None or payload.configuration_schema is None:
            raise ValueError("Application program implementation is missing")
        configuration = payload.configuration_schema.resolve().model_validate(
            implementation.config, by_name=True
        )
        output = await payload.application_function.resolve()(
            RunEngineProgramRuntime(
                operations,
                payload.children,
                payload.specifications,
                context,
                payload.element_target,
                payload.receiver,
                payload.cancellation,
            ),
            payload.inputs,
            configuration,
        )
    try:
        Draft202012Validator(definition.output_schema).validate(output)
    except SchemaValidationError as error:
        raise InvocationContractError(
            f"Program output violates its contract: {error.message}"
        ) from error
    return output


def map_program_inputs(state: ProgramGraphState, template: dict, *, bindings: dict) -> dict:
    configuration = MappingConfiguration(bindings=bindings)
    result = dict(template)
    result["inputs"] = project(configuration.bindings, state.serialize())
    return result


def map_program_outputs(
    state: ProgramGraphState, result: JsonValue, *, bindings: dict
) -> ProgramGraphState:
    configuration = MappingConfiguration(bindings=bindings)
    changes = project(configuration.bindings, result)
    unknown = changes.keys() - type(state).model_fields.keys()
    if unknown:
        raise ValueError(f"Program output targets unknown state channels: {sorted(unknown)}")
    return state.with_updates(changes)
