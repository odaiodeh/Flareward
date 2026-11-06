"""A native scheduled-entry handoff preserves the original template's admission metadata."""

from datetime import UTC, datetime
from unittest.mock import create_autospec

from inbound.run_engine.schedules import execute_scheduled_program
from mas.application.execution.models import PreparedExecution
from mas.domain.execution.context import ExecutionContext
from mas.domain.programs.models import ApplicationDefinition
from mas.scheduling.programs import ProgramSchedule, ScheduleRegistration
from run_engine.scheduling import ScheduledProgramInput
from runengine.coordination.ports import CoordinationOperations
from runengine.core.refs import FunctionRef
from support.scenarios import publish
from support.scheduling import schedule_request

from bootstrap.scheduling import admit_scheduled_execution


async def test_scheduled_entrypoint_carries_frozen_profiles_to_actual_tick_admission(platform):
    revision = await publish(
        platform, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
    )
    request = schedule_request(revision.reference)
    context = ExecutionContext(
        identity=platform.owner,
        execution_id="template",
        root_execution_id="template",
        engine_handle="template",
    )
    template = await platform.gateway.prepare(revision, request.inputs, context, "template")
    definition = ProgramSchedule(schedule_id="schedule", owner=platform.owner, request=request)
    action = ScheduledProgramInput(
        registration=ScheduleRegistration(definition=definition, prepared=template),
        admission=FunctionRef.from_callable(admit_scheduled_execution),
    )
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.run_id = "actual-tick"
    operations.now.return_value = datetime(2026, 11, 4, tzinfo=UTC)
    received = []

    async def admit(call, *, target):
        received.append(PreparedExecution.model_validate(call.kwargs["prepared"]))
        return call.kwargs["context"]

    operations.invoke.side_effect = admit
    assert await execute_scheduled_program(operations, action.model_dump(mode="json")) == {
        "answer": "hello scheduled"
    }
    assert len(received) == 1
    assert received[0].admitted_profiles == template.admitted_profiles
    assert received[0].work_limits == template.work_limits
    assert received[0].content_digest != template.content_digest
