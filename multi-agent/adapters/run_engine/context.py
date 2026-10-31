"""Bind immutable compiled context to actual engine runs at the receiving boundary."""

from mas.core.execution_context import ExecutionContext
from runengine.coordination.models import RunRequest
from runengine.programs.graph.inputs import GraphProgramInput

from run_engine.models import ElementCall, ProgramPayload


def current_context(compiled: ExecutionContext, run_id: str) -> ExecutionContext:
    same_run = compiled.engine_handle == run_id
    execution_id = compiled.execution_id if same_run and compiled.execution_id else run_id
    return compiled.model_copy(
        update={
            "execution_id": execution_id,
            "engine_handle": run_id,
            "root_execution_id": compiled.root_execution_id or execution_id,
            "parent_execution_id": compiled.parent_execution_id
            if same_run
            else compiled.execution_id or None,
            "ancestor_execution_ids": compiled.ancestor_execution_ids
            if same_run
            else (*compiled.ancestor_execution_ids, compiled.execution_id),
        }
    )


def child_request(request: RunRequest, parent: ExecutionContext) -> RunRequest:
    payload = ProgramPayload.model_validate(request.input)
    payload = payload.model_copy(update={"context": parent}, deep=True)
    return request.model_copy(update={"input": payload.model_dump(mode="json")}, deep=True)


def graph_context(
    specification: GraphProgramInput,
    context: ExecutionContext,
) -> GraphProgramInput:
    arguments = {}
    for uid, configuration in specification.arguments.items():
        if "call" not in configuration.kwargs:
            arguments[uid] = configuration
            continue
        call = ElementCall.model_validate(configuration.kwargs["call"])
        call = call.model_copy(update={"context": context})
        arguments[uid] = configuration.model_copy(
            update={
                "kwargs": {
                    **configuration.kwargs,
                    "call": call.model_dump(mode="json"),
                }
            }
        )
    programs = {
        uid: program.model_copy(update={"request": child_request(program.request, context)})
        for uid, program in specification.programs.items()
    }
    return specification.model_copy(
        update={"arguments": arguments, "programs": programs}, deep=True
    )
