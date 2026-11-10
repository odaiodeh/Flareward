"""Application lifecycle contracts use a strict gateway port double, without an SDK."""

import asyncio
import json
from unittest.mock import create_autospec

import pytest
from support.scenarios import publish

from lumora.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from lumora.executions.domain.access import WorkflowAccess
from lumora.executions.domain.budgets import WorkLimits
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import (
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
    SubmissionState,
)
from lumora.executions.domain.preferences import ExecutionProfileCatalog
from lumora.executions.models import PreparedExecution, StartExecution
from lumora.executions.ports import (
    ExecutionCancellation,
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ProgramExecutionGateway,
    SubmissionUnconfirmed,
)
from lumora.executions.service import ExecutionService
from lumora.programs.domain.models import ApplicationDefinition
from lumora.services.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from lumora.services.access.credentials import WorkflowCredentialUnavailable
from lumora.services.identity.domain import Identity


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


@pytest.fixture
def workflow_execution_case(application, execution_case):
    _, gateway, request, records = execution_case
    issuer = create_autospec(WorkflowAccessIssuer, instance=True)
    issuer.purpose = "review@1"
    service = ExecutionService(
        application.programs,
        records,
        gateway,
        workflow_access=WorkflowAccessService((issuer,)),
    )
    request = request.model_copy(
        update={
            "workflow_access": (
                WorkflowAccess(
                    purpose="review@1",
                    scope={"policies": ["release@1"], "actions": ["open", "read"]},
                ),
            )
        }
    )
    return service, gateway, request, records, issuer


async def test_portable_credential_user_is_not_workflow_approval(
    application, workflow_execution_case
):
    service, gateway, request, records, issuer = workflow_execution_case
    with pytest.raises(PermissionError, match="human approval"):
        await service.start(request, application.owner, credential_user_id=application.owner.id)
    gateway.prepare.assert_not_awaited()
    issuer.provision_workflow_access.assert_not_awaited()
    with pytest.raises(KeyError):
        await records.get(request.execution_id)


async def test_provisioning_retry_reuses_frozen_approval_before_native_dispatch(
    application, workflow_execution_case
):
    service, gateway, request, records, issuer = workflow_execution_case
    issuer.provision_workflow_access.side_effect = [WorkflowCredentialUnavailable(), None]
    first = await service.start(request, application.owner, approved_by=application.owner)
    assert first.submission == SubmissionState.UNCONFIRMED
    assert first.workflow_access_approval.approved_by.owns(application.owner)
    gateway.start.assert_not_awaited()
    gateway.status.side_effect = ExecutionMissing("Not dispatched")
    second = await service.start(request, application.owner)
    assert second.submission == SubmissionState.ACCEPTED
    assert second.workflow_access_approval == first.workflow_access_approval
    calls = issuer.provision_workflow_access.await_args_list
    assert len(calls) == 2 and calls[0] == calls[1]
    gateway.prepare.assert_awaited_once()
    gateway.start.assert_awaited_once()
    assert (
        await records.get(request.execution_id)
    ).workflow_access_approval == first.workflow_access_approval


async def test_existing_root_cannot_widen_its_workflow_access(application, workflow_execution_case):
    service, _, request, _, issuer = workflow_execution_case
    await service.start(request, application.owner, approved_by=application.owner)
    widened = request.workflow_access[0].model_copy(
        update={
            "scope": {"policies": ["release@1", "other@1"], "actions": ["open", "read", "close"]}
        }
    )
    with pytest.raises(PermissionError, match="approval does not match"):
        await service.start(
            request.model_copy(update={"workflow_access": (widened,)}),
            application.owner,
            approved_by=application.owner,
        )
    issuer.provision_workflow_access.assert_awaited_once()


async def test_approval_cannot_move_to_another_invocation(application, workflow_execution_case):
    service, gateway, request, _, issuer = workflow_execution_case
    approval = service.approve_workflow_access(request, application.owner, application.owner)
    with pytest.raises(PermissionError, match="approval does not match"):
        await service.start(
            request.model_copy(update={"execution_id": "foreign-root"}),
            application.owner,
            workflow_access_approval=approval,
        )
    gateway.prepare.assert_not_awaited()
    issuer.provision_workflow_access.assert_not_awaited()


async def test_cancellation_during_provisioning_does_not_dispatch(
    application, workflow_execution_case
):
    service, gateway, request, records, issuer = workflow_execution_case
    entered, release = asyncio.Event(), asyncio.Event()

    async def provision(*args, **kwargs):
        entered.set()
        await release.wait()

    issuer.provision_workflow_access.side_effect = provision
    task = asyncio.create_task(
        service.start(request, application.owner, approved_by=application.owner)
    )
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            await records.request_cancellation(request.execution_id)
            release.set()
            result = await task
        assert result.phase == ExecutionPhase.CANCELLED and result.cancel_requested
        gateway.start.assert_not_awaited()
    finally:
        release.set()
        await task


@pytest.mark.parametrize("values", [(True, 1), (1, 1.0)])
@pytest.mark.parametrize("concurrent", [False, True])
async def test_root_identity_preserves_json_types(application, execution_case, values, concurrent):
    service, gateway, original, records = execution_case
    requests = tuple(
        original.model_copy(update={"inputs": {"name": {"nested": [value]}}}) for value in values
    )
    if concurrent:
        prepare = gateway.prepare.side_effect
        barrier = asyncio.Barrier(2)

        async def simultaneous_prepare(*args):
            await barrier.wait()
            return await prepare(*args)

        gateway.prepare.side_effect = simultaneous_prepare
        outcomes = await asyncio.gather(
            *(service.start(request, application.owner) for request in requests),
            return_exceptions=True,
        )
        assert sum(isinstance(value, ExecutionRecord) for value in outcomes) == 1
        assert sum(isinstance(value, ValueError) for value in outcomes) == 1
    else:
        await service.start(requests[0], application.owner)
        with pytest.raises(ValueError, match="different request"):
            await service.start(requests[1], application.owner)
    saved = await records.get(original.execution_id)
    assert saved.submission == SubmissionState.ACCEPTED
    gateway.start.assert_awaited_once()
    retried = await service.start(
        original.model_copy(update={"inputs": saved.inputs}), application.owner
    )
    assert retried.execution_id == saved.execution_id


async def test_root_retry_accepts_reordered_json_object_keys(application, execution_case):
    service, gateway, request, _ = execution_case
    original = request.model_copy(update={"inputs": {"name": "value", "other": True}})
    await service.start(original, application.owner)
    repeated = original.model_copy(update={"inputs": {"other": True, "name": "value"}})
    assert (await service.start(repeated, application.owner)).submission == SubmissionState.ACCEPTED
    gateway.start.assert_awaited_once()


async def test_root_retry_preserves_original_admitted_limits_and_profiles(
    application, execution_case
):
    service, gateway, request, records = execution_case
    original = WorkLimits(max_dispatches=5)
    profiles = ExecutionProfileCatalog(profiles=("original",), default_profile="original")
    gateway.prepare.side_effect = None
    gateway.prepare.return_value = PreparedExecution(
        format="test/1",
        location=gateway.location,
        payload_json='{"original":true}',
        work_limits=original,
        admitted_profiles=profiles,
    )
    started = await service.start(request, application.owner)
    assert started.work_limits == original
    assert started.admitted_profiles == profiles
    gateway.prepare.return_value = PreparedExecution(
        format="test/1",
        location=gateway.location,
        payload_json='{"new":true}',
        work_limits=WorkLimits(max_dispatches=1),
        admitted_profiles=ExecutionProfileCatalog(profiles=("changed",), default_profile="changed"),
    )
    retried = await service.start(request, application.owner)
    assert retried.work_limits == original
    assert retried.admitted_profiles == profiles
    assert (await records.get_prepared(request.execution_id)).work_limits == original
    gateway.prepare.assert_awaited_once()


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
    revision = await application.programs.revision(request.program, application.owner)
    assert record.content_digest == revision.content_digest
    gateway.prepare.assert_not_awaited()
    gateway.start.assert_not_awaited()
    gateway.cancel.assert_not_awaited()


async def test_mutated_nonfinite_input_is_refused_before_snapshot_or_gateway_use(
    application, execution_case
):
    service, gateway, request, records = execution_case
    assert isinstance(request.inputs, dict)
    request.inputs["bad"] = float("nan")
    with pytest.raises(ValueError):
        await service.start(request, application.owner)
    gateway.prepare.assert_not_awaited()
    gateway.start.assert_not_awaited()


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
