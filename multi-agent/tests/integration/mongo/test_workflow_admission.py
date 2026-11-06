"""Partial root provisioning recovers with actual stores and application-owned ports."""

import asyncio
import json
from unittest.mock import create_autospec

import pytest
from mas.application.access.admission import WorkflowAccessIssuer, WorkflowAccessService
from mas.application.access.credentials import WorkflowCredentialUnavailable
from mas.application.execution.access import ExecutionGrantAccess
from mas.application.execution.models import PreparedExecution, StartExecution
from mas.application.execution.ports import ExecutionMissing, ProgramExecutionGateway
from mas.application.execution.service import ExecutionService
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.models import ExecutionPhase, SubmissionState
from mas.domain.programs.models import ApplicationDefinition
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.workflow_credentials import FileWorkflowCredentials
from support.managed_access import managed_access_settings
from support.managed_workflow import workflow_requirements
from support.scenarios import publish

from bootstrap.workflow_access import WorkflowAccessComponents


class InterruptedIssuer:
    """Inject uncertain delivery at one owned port, preserving real issuance behavior."""

    def __init__(self, issuer: WorkflowAccessIssuer, *, after: bool, lose_reply: bool) -> None:
        self.purpose = issuer.purpose
        self._issuer, self._after, self._lose_reply = issuer, after, lose_reply
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    def authorize_workflow_access(
        self, requirement: WorkflowAccess, root: str, owner: Identity, issued_by: Identity
    ) -> None:
        self._issuer.authorize_workflow_access(requirement, root, owner, issued_by)

    async def provision_workflow_access(
        self,
        requirement: WorkflowAccess,
        root: str,
        owner: Identity,
        issued_by: Identity,
        *,
        key: str,
    ) -> None:
        if self._after:
            await self._issuer.provision_workflow_access(
                requirement, root, owner, issued_by, key=key
            )
        self.entered.set()
        await self.release.wait()
        if self._lose_reply:
            raise WorkflowCredentialUnavailable()
        if not self._after:
            await self._issuer.provision_workflow_access(
                requirement, root, owner, issued_by, key=key
            )


@pytest.mark.parametrize("after", [False, True], ids=["partial", "lost-acknowledgment"])
@pytest.mark.parametrize("resolution", ["retry", "cancel", "cancel-in-flight", "withdraw-policy"])
async def test_partial_multipurpose_admission_recovers_without_duplicate_authority(
    application, mongo_database, tmp_path, after, resolution
):
    settings = managed_access_settings(application.owner, mongo_database.name, "", tmp_path)
    records = MongoExecutionRepository(mongo_database)
    await records.initialize()
    gateway = create_autospec(ProgramExecutionGateway, instance=True)
    gateway.location = "test-private-coordination"
    gateway.prepare.return_value = PreparedExecution(
        format="test/1", location=gateway.location, payload_json='{"frozen":true}'
    )
    gateway.status.side_effect = ExecutionMissing("No dispatch before provisioning")
    authority = ExecutionGrantAccess(records, gateway)
    components = await WorkflowAccessComponents.create(settings, mongo_database, authority)
    assert components.reviews is not None and components.verifications is not None
    interrupted = InterruptedIssuer(
        components.verifications, after=after, lose_reply=resolution != "cancel-in-flight"
    )
    service = ExecutionService(
        application.programs,
        records,
        gateway,
        workflow_access=WorkflowAccessService((components.reviews, interrupted)),
    )
    revision = await publish(
        application, "admitted", ApplicationDefinition(implementation="waiting", version="1")
    )
    request = StartExecution(
        program=revision.reference,
        execution_id="multipurpose-root",
        workflow_access=workflow_requirements(),
    )
    first_task = asyncio.create_task(
        service.start(request, application.owner, approved_by=application.owner)
    )
    try:
        async with asyncio.timeout(10):
            await interrupted.entered.wait()
            original = await records.get(request.execution_id)
            assert original.submission == SubmissionState.STARTING
            contenders = await asyncio.gather(
                *(service.start(request, application.owner) for _ in range(8))
            )
            assert all(value.submission == SubmissionState.STARTING for value in contenders)
            gateway.start.assert_not_awaited()
            partial = {
                row["_id"]: row
                async for row in mongo_database.workflow_credential_material.find({})
            }
            assert len(partial) == (2 if after else 1)
            if resolution == "cancel-in-flight":
                await records.request_cancellation(request.execution_id)
            interrupted.release.set()
            first = await first_task
    finally:
        interrupted.release.set()
        await first_task
    if resolution == "cancel-in-flight":
        assert first.phase == ExecutionPhase.CANCELLED
    else:
        assert first.submission == SubmissionState.UNCONFIRMED
    gateway.start.assert_not_awaited()
    if resolution == "cancel":
        await service.cancel(request.execution_id, application.owner)
    if resolution == "withdraw-policy":
        settings = settings.model_copy(update={"verification_policies": {}})
    # Reconstruct all application/purpose services: only persisted authority survives.
    recovered = await WorkflowAccessComponents.create(settings, mongo_database, authority)
    service = ExecutionService(
        application.programs, records, gateway, workflow_access=recovered.admission
    )
    await asyncio.gather(*(service.start(request, application.owner) for _ in range(12)))
    final = await records.get(request.execution_id)
    assert final.workflow_access_approval == original.workflow_access_approval
    assert await records.get_prepared(request.execution_id) == gateway.prepare.return_value
    gateway.prepare.assert_awaited_once()
    if resolution == "retry":
        assert final.submission == SubmissionState.ACCEPTED
        gateway.start.assert_awaited_once()
        assert await mongo_database.workflow_credential_material.count_documents({}) == 2
    else:
        assert final.phase == (
            ExecutionPhase.CANCELLED
            if resolution in {"cancel", "cancel-in-flight"}
            else ExecutionPhase.FAILED
        )
        gateway.start.assert_not_awaited()
        assert final.failure is None or final.failure.code == "workflow_access_denied"
        assert recovered.retirement is not None
        await recovered.retirement.reconcile()
        assert not list(settings.workflow_credential_directory.rglob("*.json"))
    for binding, before in partial.items():
        row = await mongo_database.workflow_credential_material.find_one({"_id": binding})
        assert row["data"] == before["data"]
        if resolution == "retry":
            assert row["credential"] == before["credential"]
        else:
            assert row["retired"] and not row["cleanup_pending"] and "credential" not in row
    if resolution == "retry":
        delivery = FileWorkflowCredentials(settings.workflow_credential_directory)
        for requirement in request.workflow_access:
            credential = await delivery.resolve(
                requirement.purpose, application.owner, request.execution_id
            )
            assert credential.get_secret_value() not in json.dumps(final.model_dump(mode="json"))
        # No revival after cancellation of a successfully recovered root.
        await records.request_cancellation(request.execution_id)
        assert recovered.retirement is not None
        await recovered.retirement.reconcile()
        assert not list(settings.workflow_credential_directory.rglob("*.json"))
