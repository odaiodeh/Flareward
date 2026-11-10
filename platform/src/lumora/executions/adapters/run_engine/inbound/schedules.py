"""One recurring tick executes its program inside the generic engine's owning run."""

from pydantic import JsonValue
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ThreadRunnerConfig
from runengine.invocation.models import InvocationRequest

from lumora.executions.adapters.run_engine.inbound.programs import execute_program
from lumora.executions.adapters.run_engine.shared.models import ProgramPayload
from lumora.executions.adapters.run_engine.shared.scheduling import ScheduledProgramInput
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.models import PreparedExecution
from lumora.services.scheduling.admission import scheduled_execution_id

__runengine_contract__ = "lumora-scheduled-program-v2"


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
        work_limits=template.work_limits,
        admitted_profiles=template.admitted_profiles,
        placement=template.placement,
    )
    admitted = await operations.invoke(
        InvocationRequest(
            function=action.admission,
            kwargs={
                "registration": action.registration.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
                "prepared": prepared.model_dump(mode="json"),
            },
        ),
        target=ThreadRunnerConfig(),
    )
    payload = payload.model_copy(update={"context": ExecutionContext.model_validate(admitted)})
    return await execute_program(operations, payload.model_dump(mode="json"))
