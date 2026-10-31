"""Application lifecycle contracts use a strict gateway port double, without an SDK."""

import json
from unittest.mock import create_autospec

import pytest
from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.execution.models import (
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
    PreparedExecution,
    StartExecution,
    SubmissionState,
)
from mas.execution.ports import (
    ExecutionCancellation,
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ProgramExecutionGateway,
    SubmissionUnconfirmed,
)
from mas.execution.service import ExecutionService
from mas.programs.models import ApplicationDefinition
from outbound.memory.execution_repository import MemoryExecutionRepository
from support.scenarios import publish


@pytest.fixture
async def execution_case(application):
    revision = await publish(
        application,
        "greeting",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.location = "test-coordination-location"

    async def prepare(revision, inputs, context, execution_id):
        return PreparedExecution(
            format="test/1",
            location=gateway.location,
            payload_json=json.dumps(
                {
                    "execution_id": execution_id,
                    "inputs": inputs,
                }
            ),
        )

    gateway.prepare.side_effect = prepare
    gateway.status.return_value = ExecutionPhase.RUNNING
    gateway.children.return_value = []
    records = MemoryExecutionRepository()
    service = ExecutionService(application.programs, records, gateway)
    return (
        service,
        gateway,
        StartExecution(
            program=revision.reference,
            inputs={"name": "input"},
            execution_id="stable",
        ),
        records,
    )


async def test_ambiguous_start_reconnects_through_port_without_repreparing(
    application, execution_case
):
    service, gateway, request, records = execution_case
    gateway.start.side_effect = SubmissionUnconfirmed(
        ExecutionFailure(
            kind=FailureKind.INFRASTRUCTURE,
            message="Reply lost",
            retryable=True,
        )
    )
    record = await service.start(request, application.owner)
    assert record.submission == SubmissionState.UNCONFIRMED
    gateway.status.return_value = ExecutionPhase.COMPLETED
    gateway.result.return_value = {"answer": "recovered"}
    result = await service.result(record.execution_id, application.owner)
    assert result.result == {"answer": "recovered"}
    gateway.prepare.assert_awaited_once()
    gateway.start.assert_awaited_once()


async def test_cancellation_before_submission_prevents_any_gateway_start(
    application, execution_case
):
    service, gateway, request, records = execution_case
    context = ExecutionContext(identity=application.owner)
    await service.prevent_start(request, application.owner, context)
    record = await service.start(request, application.owner)
    assert record.phase == ExecutionPhase.CANCELLED
    gateway.prepare.assert_not_awaited()
    gateway.start.assert_not_awaited()
    gateway.cancel.assert_not_awaited()


async def test_engine_cancellation_is_attempted_if_application_wait_cleanup_fails(
    application, execution_case
):
    service, gateway, request, records = execution_case
    await service.start(request, application.owner)
    cancellation = create_autospec(ExecutionCancellation, instance=True)
    cancellation.cancel.side_effect = OSError("Interaction service is down")
    recovering = ExecutionService(application.programs, records, gateway, cancellation)
    with pytest.raises(OSError, match="Interaction service is down"):
        await recovering.cancel(request.execution_id, application.owner)
    gateway.cancel.assert_awaited_once()


@pytest.mark.parametrize("mismatch", ["owner", "root", "session", "parent"])
async def test_child_projection_rejects_facts_outside_parent_scope(
    application, execution_case, mismatch
):
    service, gateway, request, records = execution_case
    parent = await service.start(request, application.owner)
    owner = Identity.user("other") if mismatch == "owner" else application.owner
    root_id = "another-root" if mismatch == "root" else parent.execution_id
    parent_id = "another-parent" if mismatch == "parent" else parent.execution_id
    session_id = "another-session" if mismatch == "session" else None
    child = ExecutionRecord(
        execution_id="observed-child",
        location=parent.location,
        owner=owner,
        program=request.program,
        inputs={},
        context=ExecutionContext(
            identity=owner,
            execution_id="observed-child",
            engine_handle="child-native",
            root_execution_id=root_id,
            parent_execution_id=parent_id,
            ancestor_execution_ids=(root_id, parent_id) if parent_id != root_id else (root_id,),
            session_id=session_id or "",
        ),
        parent_execution_id=parent_id,
        session_id=session_id,
        phase=ExecutionPhase.RUNNING,
        submission=SubmissionState.ACCEPTED,
    )
    gateway.children.return_value = [child]
    with pytest.raises(ValueError, match="does not belong"):
        await service.refresh(parent.execution_id, application.owner)
    with pytest.raises(KeyError):
        await records.get(child.execution_id)


@pytest.mark.parametrize("unconfirmed", [False, True])
async def test_changed_location_never_observes_cancels_or_redelivers_existing_work(
    application, execution_case, unconfirmed
):
    service, gateway, request, records = execution_case
    if unconfirmed:
        gateway.start.side_effect = SubmissionUnconfirmed(
            ExecutionFailure(kind=FailureKind.INFRASTRUCTURE, message="Reply lost", retryable=True)
        )
    original = await service.start(request, application.owner)
    location = gateway.location
    gateway.reset_mock()
    gateway.location = "another-coordination-location"
    for operation in (
        service.start(request, application.owner),
        service.refresh(request.execution_id, application.owner),
        service.result(request.execution_id, application.owner),
        service.cancel(request.execution_id, application.owner),
        service.send(request.execution_id, "input", {}, application.owner),
    ):
        with pytest.raises(ExecutionLocationUnavailable):
            await operation
    with pytest.raises(ExecutionLocationUnavailable):
        _ = [event async for event in service.events(request.execution_id, application.owner)]
    for name in ("start", "status", "result", "cancel", "send", "children", "events"):
        getattr(gateway, name).assert_not_called()
    assert await records.get(request.execution_id) == original
    gateway.location = location
    recovered = await service.start(request, application.owner)
    assert recovered.location == location and recovered.submission == SubmissionState.ACCEPTED
    gateway.start.assert_not_awaited()


async def test_lost_observation_of_accepted_work_is_unknown_and_never_restarted(
    application, execution_case
):
    service, gateway, request, _ = execution_case
    await service.start(request, application.owner)
    gateway.status.side_effect = ExecutionMissing("Retained native run is gone")
    gateway.result.side_effect = ExecutionMissing("Retained result is gone")
    record = await service.result(request.execution_id, application.owner)
    assert record.phase == ExecutionPhase.UNKNOWN
    assert record.failure.code == "execution_observation_unavailable"
    gateway.start.assert_awaited_once()
    gateway.status.side_effect = None
    recovered = await service.refresh(request.execution_id, application.owner)
    assert recovered.phase == ExecutionPhase.RUNNING and recovered.failure is None


async def test_result_recovery_clears_transient_observation_failure(application, execution_case):
    service, gateway, request, _ = execution_case
    await service.start(request, application.owner)
    gateway.status.side_effect = ExecutionMissing("Retained native run is unavailable")
    await service.refresh(request.execution_id, application.owner)
    gateway.status.side_effect = None
    gateway.result.return_value = {"answer": "recovered"}
    recovered = await service.result(request.execution_id, application.owner)
    assert recovered.phase == ExecutionPhase.COMPLETED and recovered.failure is None
    gateway.start.assert_awaited_once()
