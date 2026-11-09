"""Schedule policy and accepted-tick admission are independent of calendar SDKs."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec

import pytest
from support.scenarios import publish
from support.scheduling import schedule_request

from flareward.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from flareward.executions.domain.budgets import WorkLimits
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.models import ExecutionPhase, SubmissionState
from flareward.executions.domain.preferences import ExecutionProfileCatalog
from flareward.executions.models import PreparedExecution
from flareward.executions.ports import ProgramExecutionGateway
from flareward.programs.domain.models import ApplicationDefinition, ProgramRef
from flareward.services.identity.domain import Identity
from flareward.services.scheduling.admission import ScheduledAdmission, scheduled_execution_id
from flareward.services.scheduling.models import ScheduleDefinition, ScheduleStatus
from flareward.services.scheduling.programs import (
    ProgramSchedule,
    ProgramScheduleBackend,
    ProgramScheduleConflict,
    ProgramScheduleError,
    ProgramScheduleService,
    ProgramScheduleView,
    program_schedule_id,
    stage_schedule,
)
from flareward.services.sessions.adapters.memory.session_store import MemorySessionStore
from flareward.services.sessions.execution.session_store import SessionStore


async def test_schedule_prepares_pinned_program_with_staged_identity_without_submitting(
    application,
):
    revision = await publish(
        application, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.prepare.return_value = PreparedExecution(
        format="test", payload_json="{}", location="test"
    )
    backend = create_autospec(ProgramScheduleBackend, instance=True)
    registered = []
    backend.create.side_effect = registered.append
    backend.get.side_effect = lambda _, owner: ProgramScheduleView(
        definition=registered[-1].definition, status=ScheduleStatus.PAUSED
    )
    service = ProgramScheduleService(application.programs, gateway, backend)
    result = await service.create(
        schedule_request(revision.reference), application.owner, credential_user_id="human"
    )
    assert result.definition.owner == application.owner
    assert registered[0].definition.request.session.program == revision.reference
    context = gateway.prepare.await_args.args[2]
    assert context.credential_user_id() == "human" and context.session_id
    assert context.tags["hitl_enabled"] is False
    gateway.start.assert_not_called()
    gateway.prepare.reset_mock()
    with pytest.raises(PermissionError):
        await service.update(
            result.definition.schedule_id,
            schedule_request(revision.reference),
            Identity.user("other"),
            expected_version=1,
        )
    gateway.prepare.assert_not_called()
    backend.replace.assert_not_called()


async def test_schedule_update_fences_versions_and_restarts_completed_budget(application):
    revision = await publish(
        application, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
    )
    original = ProgramSchedule(
        schedule_id="schedule",
        owner=application.owner,
        request=schedule_request(revision.reference),
    )
    backend = create_autospec(ProgramScheduleBackend, instance=True)
    backend.get.return_value = ProgramScheduleView(
        definition=original, status=ScheduleStatus.COMPLETED
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.prepare.return_value = PreparedExecution(format="test", payload_json="{}")
    service = ProgramScheduleService(application.programs, gateway, backend)
    with pytest.raises(ProgramScheduleConflict):
        await service.update("schedule", original.request, application.owner, expected_version=2)
    gateway.prepare.assert_not_called()
    changed = original.request.model_copy(
        update={"schedule": ScheduleDefinition(interval=timedelta(hours=2), remaining_actions=3)}
    )
    await service.update("schedule", changed, application.owner, expected_version=1)
    assert backend.replace.await_args.kwargs == {"expected_version": 1, "restart": True}
    assert backend.replace.await_args.args[0].definition.version == 2
    await service.trigger("schedule", application.owner)
    backend.trigger.assert_awaited_once_with("schedule")


async def test_scheduled_admission_recovers_partial_session_creation_without_new_execution(
    application,
):
    request = schedule_request(
        (
            await publish(
                application,
                "scheduled",
                ApplicationDefinition(implementation="greeting", version="1"),
            )
        ).reference
    )
    definition = ProgramSchedule(schedule_id="schedule", owner=application.owner, request=request)
    execution_id = scheduled_execution_id("native-tick")
    context = ExecutionContext(
        identity=application.owner,
        session_id=execution_id,
        execution_id=execution_id,
        root_execution_id=execution_id,
        engine_name="run_engine",
        engine_handle="native-tick",
    )
    prepared = PreparedExecution(
        format="test",
        payload_json="{}",
        location="original",
        work_limits=WorkLimits(max_dispatches=3),
        admitted_profiles=ExecutionProfileCatalog(
            profiles=("original",), default_profile="original"
        ),
    )
    executions = MemoryExecutionRepository()
    sessions = create_autospec(SessionStore, instance=True)
    sessions.create.side_effect = [OSError("lost session write"), True]
    admission = ScheduledAdmission(executions, sessions)
    with pytest.raises(OSError):
        await admission.admit(definition, context, prepared)
    record = await executions.get(execution_id)
    assert record.submission == SubmissionState.ACCEPTED
    assert record.work_limits == prepared.work_limits
    assert record.admitted_profiles == prepared.admitted_profiles
    await admission.admit(definition, context, prepared)
    assert len(await executions.pending()) == 1
    admitted = sessions.create.await_args.args[0]
    assert admitted.metadata.schedule_id == "schedule"
    assert admitted.execution_request.execution_id == execution_id
    assert admitted.run_context.parent_execution_id is None
    await executions.update(
        record.model_copy(update={"phase": ExecutionPhase.COMPLETED, "result": "done"})
    )
    memory = MemorySessionStore()
    await ScheduledAdmission(executions, memory).admit(definition, context, prepared)
    assert (await executions.get(execution_id)).result == "done"
    assert len(await memory.scheduled(application.owner, "schedule", limit=20)) == 1
    assert await memory.scheduled(Identity.user("other"), "schedule", limit=20) == []


def test_schedule_time_bounds_normalize_to_utc_and_reject_unknown_configuration():
    schedule = ScheduleDefinition(
        interval=timedelta(minutes=1),
        start_at=datetime(2026, 1, 1),
        end_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert schedule.start_at.tzinfo is UTC
    with pytest.raises(ValueError):
        ScheduleDefinition(interval=timedelta(minutes=1), ignored_policy="unsafe")
    with pytest.raises(ValueError):
        ScheduleDefinition(interval=timedelta(seconds=1))


async def test_schedule_creation_recovers_a_lost_reply_with_an_owner_scoped_key(application):
    revision = await publish(
        application, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.prepare.return_value = PreparedExecution(format="test", payload_json="{}")
    backend = create_autospec(ProgramScheduleBackend, instance=True)
    accepted = {}

    async def accept(registration):
        accepted[registration.definition.schedule_id] = registration
        raise ProgramScheduleError("Calendar reply lost after acceptance")

    backend.create.side_effect = accept
    backend.get.side_effect = lambda key, owner: ProgramScheduleView(
        definition=accepted[key].definition, status=ScheduleStatus.PAUSED
    )
    service = ProgramScheduleService(application.programs, gateway, backend)
    request = schedule_request(revision.reference)
    with pytest.raises(ProgramScheduleError):
        await service.create(
            request, application.owner, request_key="stable", credential_user_id="first"
        )
    view = await service.create(
        request, application.owner, request_key="stable", credential_user_id="second"
    )
    assert view.definition.schedule_id == program_schedule_id(application.owner, "stable")
    assert view.definition.schedule_id != program_schedule_id(Identity.user("other"), "stable")
    backend.create.assert_awaited_once()
    gateway.prepare.assert_awaited_once()
    assert gateway.prepare.await_args.args[2].credential_user_id() == "first"
    with pytest.raises(ProgramScheduleConflict):
        await service.create(
            request.model_copy(update={"inputs": {"name": "different"}}),
            application.owner,
            request_key="stable",
        )
    # Python equality must not silently adopt a different JSON request identity.
    for previous, changed in ((True, 1), (1, 1.0)):
        key = "typed-" + type(previous).__name__
        typed = request.model_copy(update={"inputs": {"name": previous}})
        with pytest.raises(ProgramScheduleError):
            await service.create(typed, application.owner, request_key=key)
        with pytest.raises(ProgramScheduleConflict):
            await service.create(
                typed.model_copy(update={"inputs": {"name": changed}}),
                application.owner,
                request_key=key,
            )


async def test_schedule_update_snapshots_mutable_inputs_before_awaiting_storage(application):
    revision = await publish(
        application, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
    )
    request = schedule_request(revision.reference)
    definition = ProgramSchedule(schedule_id="schedule", owner=application.owner, request=request)
    entered, release = asyncio.Event(), asyncio.Event()
    backend = create_autospec(ProgramScheduleBackend, instance=True)

    async def read(schedule_id, owner):
        entered.set()
        await release.wait()
        return ProgramScheduleView(definition=definition, status=ScheduleStatus.PAUSED)

    backend.get.side_effect = read
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.prepare.return_value = PreparedExecution(format="test", payload_json="{}")
    service = ProgramScheduleService(application.programs, gateway, backend)
    async with asyncio.timeout(1):
        update = asyncio.create_task(
            service.update("schedule", request, application.owner, expected_version=1)
        )
        await entered.wait()
        request.inputs["name"] = "concurrent mutation"
        release.set()
        await update
    assert gateway.prepare.await_args.args[1] == {"name": "scheduled"}
    assert backend.replace.await_args.args[0].definition.request.inputs == {"name": "scheduled"}


@pytest.mark.parametrize("interaction", ["data", "conversation"])
def test_scheduled_turn_uses_the_same_explicit_interaction_projection(application, interaction):
    request = schedule_request(ProgramRef(program_id="scheduled", revision=1))
    request = request.model_copy(
        update={
            "session": request.session.model_copy(update={"interaction": interaction}),
            "inputs": {"name": "scheduled", "user_prompt": "review task"},
        }
    )
    definition = ProgramSchedule(schedule_id="projected", owner=application.owner, request=request)
    record, inputs = stage_schedule(
        definition, ExecutionContext(identity=application.owner, session_id="tick"), "human"
    )
    assert inputs == request.inputs
    assert record.state["name"] == "scheduled"
    if interaction == "data":
        assert record.graph_state is None
    else:
        assert record.graph_state.messages[0].content == "review task"
