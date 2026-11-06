"""Recurring source consent is private authority, not a claim in portable schedule data."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, create_autospec

import pytest
from mas.application.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from mas.application.access.consent import WorkflowConsentRequest, WorkflowConsents
from mas.application.access.credentials import WorkflowCredentialUnavailable
from mas.application.execution.models import PreparedExecution, StartExecution
from mas.application.execution.ports import ProgramExecutionGateway
from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.context import ExecutionContext
from mas.domain.programs.models import ApplicationDefinition
from mas.scheduling.admission import ScheduledAdmission, scheduled_execution_id
from mas.scheduling.models import ScheduleStatus
from mas.scheduling.programs import (
    ProgramSchedule,
    ProgramScheduleBackend,
    ProgramScheduleService,
    ProgramScheduleView,
    ScheduleRegistration,
)
from mas.session.execution.session_store import SessionStore
from outbound.memory.execution_repository import MemoryExecutionRepository
from support.scenarios import publish
from support.scheduling import schedule_request
from support.verification import VerificationClock
from support.workflow_consents import MemoryWorkflowConsents, assert_consent_store_contract


@pytest.fixture
async def consent_case(application):
    owner = application.owner
    reference = (
        await publish(
            application, "scheduled", ApplicationDefinition(implementation="greeting", version="1")
        )
    ).reference
    clock = VerificationClock(now=datetime.now(UTC))
    issuer = create_autospec(WorkflowAccessIssuer, instance=True)
    issuer.purpose = "review@1"
    access = WorkflowAccessService((issuer,), clock=clock)
    store = MemoryWorkflowConsents()
    consents = WorkflowConsents(store, access, clock=clock)
    requirement = WorkflowAccess(
        purpose="review@1", scope={"policies": ["release@1"], "actions": ["open", "read"]}
    )
    request = schedule_request(reference).model_copy(
        update={
            "workflow_access": WorkflowConsentRequest(
                requirements=(requirement,), expires_at=clock.now + timedelta(hours=1)
            )
        }
    )
    definition = ProgramSchedule(schedule_id="schedule", owner=owner, request=request)
    prepared = PreparedExecution(format="test", payload_json="{}", location="test")
    consent = await consents.approve(
        request.workflow_access,
        definition.schedule_id,
        definition.model_dump(mode="json"),
        prepared.content_digest,
        StartExecution(program=reference, execution_id="template", inputs=request.inputs),
        owner,
        owner,
    )
    registration = ScheduleRegistration(
        definition=definition, prepared=prepared, authorization_id=consent.consent_id
    )
    calendar = create_autospec(ProgramScheduleBackend, instance=True)
    calendar.registration.return_value = registration
    records = MemoryExecutionRepository()
    sessions = create_autospec(SessionStore, instance=True)
    sessions.create.return_value = True
    native = "native-recurring-root"
    root = scheduled_execution_id(native)
    context = ExecutionContext(
        identity=owner,
        execution_id=root,
        root_execution_id=root,
        session_id=root,
        engine_handle=native,
        tags={"credential_user_id": "untrusted-tag"},
    )
    admission = ScheduledAdmission(
        records, sessions, consents=consents, workflow_access=access, calendar=calendar
    )
    return (
        owner,
        clock,
        issuer,
        store,
        consents,
        registration,
        calendar,
        records,
        sessions,
        context,
        admission,
    )


async def test_consent_store_preserves_human_audit_and_owner_type_scope(consent_case):
    owner, _, _, store, consents, registration, *_ = consent_case
    consent = await consents.get(registration.authorization_id, owner)
    fresh = consent.model_copy(update={"consent_id": "f" * 32})
    await assert_consent_store_contract(store, fresh)


async def test_partial_session_write_recovers_original_consent_and_issuance_intent(consent_case):
    owner, _, issuer, _, consents, registration, _, records, sessions, context, admission = (
        consent_case
    )
    sessions.create.side_effect = [OSError("lost acknowledgement"), True]
    with pytest.raises(OSError):
        await admission.admit(
            registration.definition, context, registration.prepared, registration=registration
        )
    first = await records.get(context.execution_id)
    consent = await consents.get(registration.authorization_id, owner)
    assert first.workflow_access_approval.approved_by == consent.approved_by
    assert first.workflow_access_approval.approved_by.id != context.credential_user_id()
    assert first.workflow_access_approval.approved_at == consent.approved_at
    await admission.admit(
        registration.definition, context, registration.prepared, registration=registration
    )
    assert (
        await records.get(context.execution_id)
    ).workflow_access_approval == first.workflow_access_approval
    calls = issuer.provision_workflow_access.await_args_list
    assert len(calls) == 2 and calls[0] == calls[1]
    assert (
        sessions.create.await_args.args[0].workflow_access_approval
        == first.workflow_access_approval
    )


@pytest.mark.parametrize("change", ["expired", "revoked", "definition", "prepared", "superseded"])
async def test_unattended_admission_refuses_missing_current_consent_before_material(
    consent_case, change
):
    owner, clock, issuer, _, consents, registration, calendar, records, _, context, admission = (
        consent_case
    )
    if change == "expired":
        clock.advance(3601)
    elif change == "revoked":
        await consents.revoke(registration.authorization_id, owner)
    elif change == "definition":
        changed = registration.definition.model_copy(
            update={
                "request": registration.definition.request.model_copy(
                    update={"inputs": {"name": "tampered"}}
                )
            }
        )
        registration = registration.model_copy(update={"definition": changed})
        calendar.registration.return_value = registration
    elif change == "prepared":
        registration = registration.model_copy(
            update={"prepared": PreparedExecution(format="test", payload_json='{"changed":true}')}
        )
        calendar.registration.return_value = registration
    else:
        calendar.registration.return_value = registration.model_copy(
            update={"authorization_id": "0" * 32}
        )
    with pytest.raises(PermissionError):
        await admission.admit(
            registration.definition, context, registration.prepared, registration=registration
        )
    issuer.provision_workflow_access.assert_not_awaited()
    with pytest.raises(KeyError):
        await records.get(context.execution_id)


async def test_schedule_creation_stores_consent_without_provisioning_tokens(
    application, consent_case, monkeypatch
):
    owner, _, issuer, _, consents, registration, calendar, *_ = consent_case
    registered = []
    calendar.create.side_effect = registered.append
    calendar.get.side_effect = lambda *args: ProgramScheduleView(
        definition=registered[-1].definition,
        authorization_id=registered[-1].authorization_id,
        status=ScheduleStatus.PAUSED,
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.prepare.return_value = registration.prepared
    service = ProgramScheduleService(application.programs, gateway, calendar, consents)
    with pytest.raises(PermissionError, match="human consent"):
        await service.create(registration.definition.request, owner, credential_user_id=owner.id)
    calendar.create.assert_not_awaited()
    view = await service.create(registration.definition.request, owner, approved_by=owner)
    assert view.workflow_access_consent.approved_by.owns(owner)
    calendar.list.return_value = [view.model_copy(update={"workflow_access_consent": None})]
    assert (await service.list(owner))[0].workflow_access_consent == view.workflow_access_consent
    issuer.provision_workflow_access.assert_not_awaited()
    await service.revoke_workflow_access(view.definition.schedule_id, owner)
    assert (await consents.get(view.authorization_id, owner)).revoked
    assert (await service.list(owner))[0].workflow_access_consent.revoked
    monkeypatch.setattr(consents, "get", AsyncMock(side_effect=WorkflowCredentialUnavailable()))
    with pytest.raises(WorkflowCredentialUnavailable):
        await service.get(view.definition.schedule_id, owner)
    await service.delete(view.definition.schedule_id, owner)
    calendar.delete.assert_awaited_once_with(view.definition.schedule_id)
    with pytest.raises(PermissionError):
        await service.delete(
            view.definition.schedule_id, owner.model_copy(update={"id": "foreign"})
        )
