"""Root authority observes liveness without resubmitting or expanding executions."""

from unittest.mock import create_autospec

import pytest

from flareward.executions.access import ExecutionGrantAccess
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.models import ExecutionPhase, ExecutionRecord, SubmissionState
from flareward.executions.ports import (
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ExecutionRepository,
    ProgramExecutionGateway,
)
from flareward.programs.domain.models import ProgramRef
from flareward.services.access.executions import ExecutionAccessUnavailable
from flareward.services.identity.domain import Identity


@pytest.fixture
def execution_authority():
    owner = Identity.user("owner")
    records = create_autospec(ExecutionRepository, instance=True)
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.location = "authority-location"
    record = ExecutionRecord(
        execution_id="root",
        owner=owner,
        inputs={},
        program=ProgramRef(program_id="program", revision=1),
        context=ExecutionContext(
            identity=owner, execution_id="root", root_execution_id="root", engine_handle="native"
        ),
        phase=ExecutionPhase.RUNNING,
        submission=SubmissionState.ACCEPTED,
        location=gateway.location,
    )
    records.get.return_value = record
    gateway.status.return_value = ExecutionPhase.RUNNING
    return owner, record, records, gateway, ExecutionGrantAccess(records, gateway)


async def test_preprovisioning_does_not_make_a_missing_root_active(execution_authority):
    owner, _, records, gateway, authority = execution_authority
    records.get.side_effect = KeyError("missing")
    assert not await authority.closed("root", owner)
    assert not await authority.active("root", owner)
    gateway.start.assert_not_awaited()
    gateway.status.assert_not_awaited()
    gateway.children.assert_not_awaited()


async def test_native_completion_denies_authority_despite_a_stale_running_projection(
    execution_authority,
):
    owner, _, _, gateway, authority = execution_authority
    assert await authority.active("root", owner)
    gateway.status.return_value = ExecutionPhase.COMPLETED
    assert not await authority.active("root", owner)
    assert await authority.closed("root", owner)


@pytest.mark.parametrize("change", ["foreign", "cancelled", "child"])
async def test_foreign_cancelled_or_child_identity_is_not_root_authority(
    execution_authority, change
):
    owner, record, records, gateway, authority = execution_authority
    if change == "foreign":
        records.get.return_value = record.model_copy(update={"owner": Identity.user("foreign")})
    else:
        records.get.return_value = record.model_copy(
            update={"cancel_requested": True}
            if change == "cancelled"
            else {"parent_execution_id": "parent"}
        )
    assert not await authority.active("root", owner)
    assert await authority.closed("root", owner)


@pytest.mark.parametrize("boundary", ["get", "status", "unknown", "location"])
async def test_unknown_native_authority_fails_closed_as_unavailable(execution_authority, boundary):
    owner, record, records, gateway, authority = execution_authority
    if boundary == "unknown":
        gateway.status.return_value = ExecutionPhase.UNKNOWN
    elif boundary == "location":
        records.get.return_value = record.model_copy(update={"location": "different"})
    else:
        getattr(
            records if boundary == "get" else gateway, boundary
        ).side_effect = ExecutionLocationUnavailable()
    with pytest.raises(ExecutionAccessUnavailable):
        await authority.active("root", owner)
    with pytest.raises(ExecutionAccessUnavailable):
        await authority.closed("root", owner)


@pytest.mark.parametrize(
    "submission", [SubmissionState.STARTING, SubmissionState.UNCONFIRMED, SubmissionState.ACCEPTED]
)
async def test_native_completion_closes_issuance_even_before_submission_ack(
    execution_authority, submission
):
    owner, record, records, gateway, authority = execution_authority
    records.get.return_value = record.model_copy(
        update={"phase": ExecutionPhase.SUBMITTING, "submission": submission}
    )
    gateway.status.return_value = ExecutionPhase.COMPLETED
    assert await authority.closed("root", owner)
    gateway.status.side_effect = ExecutionMissing("Not yet accepted")
    assert await authority.closed("root", owner) == (submission == SubmissionState.ACCEPTED)
