"""Source approval and deduplication use narrow ports and canonical root admission."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec

import pytest
from support.event_sources import MemoryEventSources, assert_event_source_store_contract
from support.managed_workflow import workflow_requirements
from support.scenarios import publish
from support.verification import VerificationClock
from support.workflow_consents import MemoryWorkflowConsents

from lumora.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from lumora.executions.domain.budgets import WorkLimits
from lumora.executions.domain.events import ProgramEvent
from lumora.executions.domain.placement import PreparedProgramPlacement
from lumora.executions.domain.preferences import ExecutionProfileCatalog
from lumora.executions.events import (
    CreateEventSource,
    EventAuthenticationError,
    EventSourceConflict,
    EventSourceUnavailable,
    ProgramEventService,
    RotateEventCredential,
)
from lumora.executions.models import PreparedExecution
from lumora.executions.ports import ExecutionRequestConflict, ProgramExecutionGateway
from lumora.executions.service import ExecutionService
from lumora.programs.domain.models import CustomCoordinatorDefinition
from lumora.services.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from lumora.services.access.consent import WorkflowConsents
from lumora.services.identity.domain import Identity


@pytest.fixture
def event_clock():
    return VerificationClock(now=datetime.now(UTC))


@pytest.fixture
async def event_case(application, event_clock):
    revision = await publish(
        application, "event", CustomCoordinatorDefinition(implementation="greeting", version="1")
    )
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.location = "private-test-location"
    template = PreparedExecution(
        format="test/1", location=gateway.location, payload_json='{"frozen":true}'
    )
    gateway.prepare.return_value = template
    gateway.bind.return_value = template
    issuer = create_autospec(WorkflowAccessIssuer, instance=True)
    issuer.purpose = "review@1"
    access = WorkflowAccessService((issuer,), clock=event_clock)
    records = MemoryExecutionRepository()
    executions = ExecutionService(application.programs, records, gateway, workflow_access=access)
    sources = MemoryEventSources()
    consents = MemoryWorkflowConsents()
    events = ProgramEventService(
        sources,
        application.programs,
        executions,
        gateway,
        consents=WorkflowConsents(consents, access, clock=event_clock),
        clock=event_clock,
    )
    request = CreateEventSource(
        name="Issues",
        program=revision.reference,
        event_type="issue@1",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        workflow_access=workflow_requirements()[:1],
    )
    return events, request, sources, records, gateway, issuer, consents


async def test_source_store_contract():
    await assert_event_source_store_contract(MemoryEventSources())


async def test_source_settings_are_frozen_owner_scoped_and_exclude_private_payload(
    application, event_case
):
    events, request, _, _, gateway, _, _ = event_case
    profiles = ExecutionProfileCatalog(profiles=("approved",), default_profile="approved")
    placement = PreparedProgramPlacement(
        program=request.program,
        default_profile="approved",
        environments={},
        dynamic_invocations=True,
    )
    gateway.prepare.return_value = PreparedExecution(
        format="test/1",
        location=gateway.location,
        payload_json='{"private":"not-public"}',
        admitted_profiles=profiles,
        work_limits=WorkLimits(max_dispatches=7),
        placement=placement,
    )
    issued = await events.create(request, application.owner, application.owner)
    gateway.prepare.return_value = PreparedExecution(format="test/1", payload_json="{}")
    settings = await events.settings(issued.source.source_id, application.owner)
    assert settings.admitted_profiles == profiles
    assert settings.work_limits == WorkLimits(max_dispatches=7)
    assert settings.placement == placement
    assert "not-public" not in settings.model_dump_json()
    with pytest.raises(KeyError):
        await events.settings(issued.source.source_id, Identity.team(application.owner.id))
    gateway.prepare.assert_awaited_once()


async def test_duplicate_events_preserve_original_approval_and_single_dispatch(
    application, event_case
):
    events, request, _, records, gateway, issuer, _ = event_case
    issued = await events.create(request, application.owner, application.owner)
    issuer.provision_workflow_access.assert_not_awaited()
    event = ProgramEvent(event_id="issue-42", event_type="issue@1", inputs={"name": "first"})
    outcomes = await asyncio.gather(
        *(events.deliver(issued.credential.get_secret_value(), event) for _ in range(10))
    )
    assert len({value.execution_id for value in outcomes}) == 1
    record = await records.get(outcomes[0].execution_id)
    assert record.inputs == event.inputs
    assert record.context.tags["event"] == {
        "source_id": issued.source.source_id,
        "event_id": "issue-42",
        "event_type": "issue@1",
    }
    assert record.workflow_access_approval.approved_by.owns(application.owner)
    assert record.workflow_access_approval.consent_id is not None
    assert record.workflow_access_approval.approved_at <= issued.source.expires_at
    gateway.start.assert_awaited_once()
    gateway.prepare.assert_awaited_once()
    issuer.provision_workflow_access.assert_awaited_once()
    assert issued.credential.get_secret_value() not in json.dumps(record.model_dump(mode="json"))
    await events.revoke(issued.source.source_id, application.owner)
    with pytest.raises(EventAuthenticationError):
        await events.deliver(issued.credential.get_secret_value(), event)
    assert (
        await records.get(record.execution_id)
    ).workflow_access_approval == record.workflow_access_approval


async def test_rotation_preserves_source_and_deduplication_but_refuses_old_credential(
    application, event_case
):
    events, request, _, records, gateway, _, _ = event_case
    issued = await events.create(request, application.owner, application.owner)
    original = issued.credential.get_secret_value()
    event = ProgramEvent(event_id="issue-42", event_type="issue@1", inputs={"name": "first"})
    first = await events.deliver(original, event)
    source_before = await events.get(issued.source.source_id, application.owner)
    settings_before = await events.settings(issued.source.source_id, application.owner)
    rotated = await events.rotate(
        issued.source.source_id, application.owner, RotateEventCredential(expected_revision=0)
    )
    assert rotated.revision == 1
    assert await events.get(issued.source.source_id, application.owner) == source_before
    assert (await events.settings(issued.source.source_id, application.owner)).placement == (
        settings_before.placement
    )
    assert (
        await events.settings(issued.source.source_id, application.owner)
    ).credential_revision == 1
    with pytest.raises(EventAuthenticationError):
        await events.deliver(original, event)
    repeated = await events.deliver(rotated.credential.get_secret_value(), event)
    assert repeated.execution_id == first.execution_id
    assert (await records.get(first.execution_id)).inputs == event.inputs
    gateway.start.assert_awaited_once()


async def test_rotation_is_owner_scoped_and_compare_and_swap(application, event_case):
    events, request, _, _, _, _, _ = event_case
    issued = await events.create(request, application.owner, application.owner)
    source_id = issued.source.source_id
    with pytest.raises(KeyError):
        await events.rotate(
            source_id,
            Identity.team(application.owner.id),
            RotateEventCredential(expected_revision=0),
        )
    results = await asyncio.gather(
        *(
            events.rotate(source_id, application.owner, RotateEventCredential(expected_revision=0))
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, EventSourceConflict) for result in results) == 1
    assert (await events.settings(source_id, application.owner)).credential_revision == 1
    await events.revoke(source_id, application.owner)
    with pytest.raises(KeyError):
        await events.rotate(
            source_id, application.owner, RotateEventCredential(expected_revision=1)
        )


async def test_lost_rotation_reply_requires_inspection_and_a_new_rotation(application, event_case):
    events, request, sources, _, _, _, _ = event_case
    issued = await events.create(request, application.owner, application.owner)
    source_id = issued.source.source_id
    original_rotate = sources.rotate

    async def committed_but_unknown(*args, **kwargs):
        await original_rotate(*args, **kwargs)
        raise EventSourceUnavailable("Event source rotation is unconfirmed")

    sources.rotate = committed_but_unknown
    with pytest.raises(EventSourceUnavailable):
        await events.rotate(
            source_id, application.owner, RotateEventCredential(expected_revision=0)
        )
    sources.rotate = original_rotate
    revision = (await events.settings(source_id, application.owner)).credential_revision
    assert revision == 1
    replacement = await events.rotate(
        source_id, application.owner, RotateEventCredential(expected_revision=revision)
    )
    assert replacement.revision == 2
    event = ProgramEvent(event_id="recovered", event_type="issue@1", inputs={"name": "first"})
    with pytest.raises(EventAuthenticationError):
        await events.deliver(issued.credential.get_secret_value(), event)
    assert (await events.deliver(replacement.credential.get_secret_value(), event)).execution_id


async def test_changed_payload_cannot_reuse_event_identity_and_sources_are_namespaced(
    application, event_case
):
    events, request, _, records, gateway, _, _ = event_case
    first, second = [
        await events.create(request, application.owner, application.owner) for _ in range(2)
    ]
    event = ProgramEvent(event_id="same-id", event_type="issue@1", inputs={"name": True})
    receipt = await events.deliver(first.credential.get_secret_value(), event)
    with pytest.raises(ExecutionRequestConflict):
        await events.deliver(
            first.credential.get_secret_value(), event.model_copy(update={"inputs": {"name": 1}})
        )
    other = await events.deliver(second.credential.get_secret_value(), event)
    assert receipt.execution_id != other.execution_id
    assert (await records.get(receipt.execution_id)).workflow_access_approval.consent_id != (
        await records.get(other.execution_id)
    ).workflow_access_approval.consent_id
    assert gateway.start.await_count == 2


@pytest.mark.parametrize("failure", ["bearer", "type", "schema", "consent", "expired"])
async def test_refused_event_does_not_bind_or_dispatch(
    application, event_case, event_clock, failure
):
    events, request, sources, _, gateway, issuer, consents = event_case
    request = request.model_copy(update={"input_schema": {"type": "object", "required": ["name"]}})
    issued = await events.create(request, application.owner, application.owner)
    event = ProgramEvent(event_id="refused", event_type="issue@1", inputs={"name": "accepted"})
    credential = issued.credential.get_secret_value()
    if failure == "bearer":
        credential = "untrusted"
    elif failure == "type":
        event = event.model_copy(update={"event_type": "other@1"})
    elif failure == "schema":
        event = event.model_copy(update={"inputs": {}})
    elif failure == "consent":
        registration = await sources.get(issued.source.source_id)
        await consents.revoke(registration.authorization_id, application.owner)
    else:
        event_clock.advance(7200)
    with pytest.raises(PermissionError if failure != "schema" else ValueError):
        await events.deliver(credential, event)
    gateway.bind.assert_not_awaited()
    gateway.start.assert_not_awaited()
    issuer.provision_workflow_access.assert_not_awaited()


async def test_source_management_requires_human_owner_and_bundled_schema(application, event_case):
    events, request, _, _, gateway, _, _ = event_case
    with pytest.raises(PermissionError):
        await events.create(request, application.owner, Identity.user("foreign"))
    with pytest.raises(ValueError, match="bundled"):
        await events.create(
            request.model_copy(update={"input_schema": {"$ref": "https://invalid.local/schema"}}),
            application.owner,
            application.owner,
        )
    gateway.prepare.assert_not_awaited()


@pytest.mark.parametrize("invalid", ["schema", "expiry"])
async def test_source_refusals_do_not_echo_submitted_values(application, event_case, invalid):
    events, request, sources, _, gateway, _, _ = event_case
    marker = "private-unparsed-event-value"
    update = (
        {"input_schema": {"type": marker}}
        if invalid == "schema"
        else {"name": marker, "expires_at": datetime.now(UTC) - timedelta(hours=1)}
    )
    with pytest.raises(ValueError) as failure:
        await events.create(request.model_copy(update=update), application.owner, application.owner)
    assert marker not in str(failure.value)
    assert sources.rows == {}
