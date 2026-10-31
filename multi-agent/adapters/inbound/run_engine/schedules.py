"""One recurring tick executes its program inside the generic engine's owning run."""

from mas.core.execution_context import ExecutionContext
from mas.execution.models import PreparedExecution
from mas.scheduling.admission import scheduled_execution_id
from pydantic import JsonValue
from run_engine.models import ProgramPayload
from run_engine.scheduling import ScheduledProgramInput
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ThreadRunnerConfig
from runengine.invocation.models import InvocationRequest

from inbound.run_engine.programs import execute_program

__runengine_contract__ = "unifai-scheduled-program-v1"


async def execute_scheduled_program(
    operations: CoordinationOperations, data: JsonValue
) -> JsonValue:
    action = ScheduledProgramInput.model_validate(data)
    template = action.registration.prepared
    request = RunRequest.model_validate_json(template.payload_json)
    payload = ProgramPayload.model_validate(request.input)
    execution_id = scheduled_execution_id(operations.run_id)
    context = payload.context.model_copy(
        update={
            "session_id": execution_id,
            "execution_id": execution_id,
            "root_execution_id": execution_id,
            "parent_execution_id": None,
            "ancestor_execution_ids": (),
            "engine_handle": operations.run_id,
            "started_at": operations.now(),
            "last_active_at": None,
            "finished_at": None,
        }
    )
    actual_request = request.model_copy(
        update={
            "program": FunctionRef.from_callable(execute_scheduled_program),
            "input": action.model_dump(mode="json"),
            "run_id": operations.run_id,
        },
        deep=True,
    )
    prepared = PreparedExecution(
        format=template.format,
        payload_json=actual_request.model_dump_json(),
        location=template.location,
    )
    admitted = await operations.invoke(
        InvocationRequest(
            function=action.admission,
            kwargs={
                "definition": action.registration.definition.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
                "prepared": prepared.model_dump(mode="json"),
            },
        ),
        target=ThreadRunnerConfig(),
    )
    payload = payload.model_copy(update={"context": ExecutionContext.model_validate(admitted)})
    return await execute_program(operations, payload.model_dump(mode="json"))
